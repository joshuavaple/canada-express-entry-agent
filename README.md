TODO
[x] Add .env for the `agent_server.py` to load to authenticate necessary interactions between the development environment and remote workspace.
    - This solves the experiment id not found errors observed when starting the server before the file was added.
[x] Troubleshoot the reading and using of Databricks secret scope to initalize the AzureChatOpenAI client in `agent.py`
    - used `dbutils` intead of `WorkspaceClient()` to read secret scope. Reason unknown.
[x] Tried the alternative LLM client `databricks_langchain.ChatDatabricks`
    - authenticated by profile loaded from .env
    - using "databricks-qwen3-next-80b-a3b-instruct"
[x] Updated the `agent_server.py` to switch between the 2 LLM client methods (by commenting in/out for now)
