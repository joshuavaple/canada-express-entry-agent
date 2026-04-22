# TODO
- [x] Add .env for the `agent_server.py` to load to authenticate necessary interactions between the development environment and remote workspace.
    - This solves the experiment id not found errors observed when starting the server before the file was added.
- [x] Troubleshoot the reading and using of Databricks secret scope to initalize the AzureChatOpenAI client in `agent.py`
    - used `dbutils` intead of `WorkspaceClient()` to read secret scope. Reason unknown.
- [x] Tried the alternative LLM client `databricks_langchain.ChatDatabricks`
    - authenticated by profile loaded from .env
    - using "databricks-qwen3-next-80b-a3b-instruct"
- [x] Updated the `agent_server.py` to switch between the 2 LLM client methods (by commenting in/out for now)
- [ ] Customize the frontend
- [ ] turn off the frontend cloning behavior in the start-app script
- [ ] how to run frontend and backend separately in 2 terminal sessions and they can still work together?

# Manual local development loop setup
1. Set up your local environment 
    - [x] Install uv (python package manager), 
    - [x] nvm (node version manager), 
    - [x] and the Databricks CLI
2. Set up local authentication to Databricks
    - [x] Option 1: OAuth via Databricks CLI (Recommended) (.env set up)
3. Create and link an MLflow experiment to your app
    - [x] Create remote experiment and get its ID
    - [x] update the MLFLOW_EXPERIMENT_ID in your .env file with the experiment ID you created.
4. Run both agent server and frontend chat UI at the same time
    - [x] use `uv run start-app` => runs `scripts/start_app.py`. This will clone the chat UI folder if it does not exist yet.
5. Run only the frontend, e.g., to customize the UI
    - [x] in `e2e-chatbot-app-next`, add the minimal `DATABRICKS_CONFIG_PROFILE` in a `.env` file. Use the same profile you used during the initial auth setup in step (2)