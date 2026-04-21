import logging
# === core agent logic ===
import trafilatura
import mlflow
# from langchain_openai.chat_models.azure import AzureChatOpenAI
from databricks_langchain import ChatDatabricks
from langchain.agents import create_agent
from langchain.tools import tool

# == wrapper for AgentServer ===
from typing import AsyncGenerator, Optional
from databricks.sdk import WorkspaceClient
from mlflow.genai.agent_server import invoke, stream
from langchain.agents import create_agent
from langchain_core.tools import tool
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    to_chat_completions_input,
)
from agent_server.utils import (
    get_databricks_host_from_env,
    get_session_id,
    get_user_workspace_client,
    process_agent_astream_events,
)


logger = logging.getLogger(__name__)
mlflow.langchain.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)

# for Databricks LLM, authentication is handled behind the scene using your Databricks profile.
llm_client = ChatDatabricks(endpoint="databricks-qwen3-next-80b-a3b-instruct")

# === System Prompt ===
SYSTEM_PROMPT = """
You are a helpful, patient and professional immigration agent that helps users answers questions on Canada Express Entry immigration system.
You are equiped with a list of tools to query the trusted information, based on which your answers must be.
However, as the content retrieved may contain more information than what is needed for the question, pick out only the necessary information to provide the answer.
If there is no tool to answer the user's question, politely decline to answer it.
"""

# === Static Tools ===
def fetch_link_content(url:str) -> str:
    downloaded = trafilatura.fetch_url(url)
    content = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_images=False,
    )
    return content

@tool("fetch_express_entry_intro_tool")
def fetch_express_entry_intro_tool(input: str = ""):
    """
    Scrapes the IRCC website for the latest introduction on the Express Entry system.
    """
    return fetch_link_content(url="https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry.html")

@tool("fetch_express_entry_documents_tool")
def fetch_express_entry_documents_tool(input: str = ""):
    """
    Scrapes the IRCC website for the latest list of documents to create a profile Express Entry system.
    """
    return fetch_link_content(url="https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents.html")

@tool("fetch_language_test_document_tool")
def fetch_language_test_document_tool(input: str = ""):
    """
    Scrapes the IRCC website for:
    - How to use the language test result in your Express Entry profile
    - List of approved language tests
    - Required language level for English and French in 3 programs under Express Entry: 
        - Federal Skilled Worker Program (FSWP)
        - Federal Skilled Trades Program (FSTP)
        - Canadian Experience Class (CEC)
    - Validity of the language test result
    """
    return fetch_link_content(url="https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/language-test.html")

@tool("direct_to_clb_ielts_converter_tool")
def direct_to_clb_ielts_converter_tool(input: str = ""):
    """
    Direct users to the external website for CLB-IELTS conversion. This tool is not maintained internally.
    """
    message = """
    To convert your IELTS score to CLB or vice-versa, please visit the following website:
    https://www.ielts.ca/take-ielts/ielts-for-canadian-immigration/ielts-to-clb/
    """
    return message

tools = [
    fetch_express_entry_intro_tool,
    fetch_express_entry_documents_tool,
    fetch_language_test_document_tool,
    direct_to_clb_ielts_converter_tool]

# tools_by_name = {tool.name: tool for tool in tools}
# agent = create_agent(model=llm_client, tools=tools, system_prompt=SYSTEM_PROMPT)



# === Wrapper ===
async def init_agent(workspace_client: Optional[WorkspaceClient] = None):
    agent = create_agent(
        model=llm_client, 
        tools=tools, 
        system_prompt=SYSTEM_PROMPT)
    return agent

@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    outputs = [
        event.item
        async for event in stream_handler(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs)

@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
        
    # By default, uses service principal credentials.
    # For on-behalf-of user authentication, use get_user_workspace_client() instead:
    #   agent = await init_agent(workspace_client=get_user_workspace_client())
    agent = await init_agent()
    messages = {"messages": to_chat_completions_input([i.model_dump() for i in request.input])}

    async for event in process_agent_astream_events(
        agent.astream(input=messages, stream_mode=["updates", "messages"])
    ):
        yield event