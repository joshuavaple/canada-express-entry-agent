import logging
# === core agent logic ===
import trafilatura
import os
import mlflow
from langchain_openai.chat_models.azure import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool

# === wrapper ResponsesAgent ===
# from typing import Generator
# from langgraph.graph.state import CompiledStateGraph
# from mlflow.models import set_model
# from mlflow.pyfunc import ResponsesAgent
# from mlflow.types.responses import (
#     ResponsesAgentRequest,
#     ResponsesAgentResponse,
#     ResponsesAgentStreamEvent,
#     output_to_responses_items_stream,
#     to_chat_completions_input,
# )

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
from databricks.sdk.runtime import dbutils

logger = logging.getLogger(__name__)
mlflow.langchain.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
# litellm.suppress_debug_info = True
sp_workspace_client = WorkspaceClient()


mlflow.langchain.autolog()


# TODO: set the following in the server environment variables:
# os.environ["AZURE_OPENAI_ENDPOINT"] = AZURE_OPENAI_ENDPOINT
# os.environ["AZURE_OPENAI_API_KEY"] = AZURE_OPENAI_API_KEY
# then this client class will be init correctly
# to test, use databricks secret scope
# AZURE_OPENAI_ENDPOINT = dbutils.secrets.get(scope="demo-scope", key="azure_openai_endpoint")
# AZURE_OPENAI_API_KEY = dbutils.secrets.get(scope="demo-scope", key="azure_openai_api_key")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
if not AZURE_OPENAI_ENDPOINT:
    sp_workspace_client
    AZURE_OPENAI_ENDPOINT = sp_workspace_client.secrets.get_secret(
        scope="demo-scope", 
        key="azure_openai_endpoint"
    ).value
    AZURE_OPENAI_API_KEY = sp_workspace_client.secrets.get_secret(
        scope="demo-scope", 
        key="azure_openai_api_key"
    ).value

os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"] = "gpt-4o"
os.environ["AZURE_OPENAI_API_VERSION"] = "2024-10-21"
os.environ["MODEL_VERSION"] = "2024-11-20"
os.environ["AZURE_OPENAI_API_KEY"] = AZURE_OPENAI_API_KEY
os.environ["AZURE_OPENAI_ENDPOINT"] = AZURE_OPENAI_ENDPOINT

llm_client = AzureChatOpenAI(
    azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
    model_version=os.environ.get("MODEL_VERSION"),
)


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
sp_workspace_client = WorkspaceClient()

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




# === Wrapper ==
# class LangGraphResponsesAgent(ResponsesAgent):
#     def __init__(self, agent: CompiledStateGraph):
#         self.agent = agent

#     def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
#         outputs = [
#             event.item
#             for event in self.predict_stream(request)
#             if event.type == "response.output_item.done"
#         ]
#         return ResponsesAgentResponse(output=outputs, custom_outputs=request.custom_inputs)

#     def predict_stream(
#         self,
#         request: ResponsesAgentRequest,
#     ) -> Generator[ResponsesAgentStreamEvent, None, None]:
#         cc_msgs = to_chat_completions_input([i.model_dump() for i in request.input])

#         for _, events in self.agent.stream({"messages": cc_msgs}, stream_mode=["updates"]):
#             for node_data in events.values():
#                 yield from output_to_responses_items_stream(node_data["messages"])


# mlflow.langchain.autolog()
# graph = agent
# wrapped_agent = LangGraphResponsesAgent(graph)
# set_model(wrapped_agent)