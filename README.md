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
- [ ] add `preflight.py` and update the `pyproject.toml` for prechecks before deployment to Databricks apps.
- [ ] add `databricks.yml` and update the following fields:
      - Compulsory: `experiment_id`, `host`
      - Optional: bundle name and app name
      - Compulsory: targets/<env>/workspace/root_path: to /Workspace/... (to resolve missing files when deploying to default home page)
      - If deployment shows error below, add the policy id to the field `budget_policy_id` inside `databricks.yml` (same level as the apps/<bundle_name>/name) (to check why)
        ```
        Deploying resources...
        Error: terraform apply: exit status 1
        
        Error: Provider produced inconsistent result after apply
        
        When applying changes to databricks_app.agent_langgraph_express_entry,
        provider "provider[\"registry.terraform.io/databricks/databricks\"]" produced
        an unexpected new value: .budget_policy_id: was null, but now
        cty.StringVal("b462f393-10df-442a-b49a-9a928118fe29").
        
        This is a bug in the provider, which should be reported in the provider's own
        issue tracker.
        ```

# Manual local development loop setup
1. Set up your local environment 
    - [x] Install uv (python package manager), 
    - [x] nvm (node version manager),
        - [x] If facing error `nvm: command not found` after installation, refer to `https://www.squash.io/how-to-solve-nvm-command-not-found-during-node-version-manager-installation/`
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
6. Run only the backend, e.g., to test the agent server's responses
    - [x] use `uv run start-server` => run `agent_server/start_server.py` on the default port 8000
    - [x] then, use curl to call the agent:
       - Example streaming request:
         ```bash
         curl -X POST http://localhost:8000/invocations \
         -H "Content-Type: application/json" \
         -d '{ "input": [{ "role": "user", "content": "hi" }], "stream": true }'
         ```
       - Example non-streaming request:
         ```bash
         curl -X POST http://localhost:8000/invocations  \
         -H "Content-Type: application/json" \
         -d '{ "input": [{ "role": "user", "content": "hi" }] }'
         ```
7. Advanced server options:
   ```bash
   uv run start-server --reload   # hot-reload the server on code changes
   uv run start-server --port 8001 # change the port the server listens on (e.g., when 8000 is occupied and cannot be killed)
   uv run start-server --workers 4 # run the server with multiple workers
   ```
8. Mitigation for "error downloading Terraform" during bundle deployments: update the Databricks CLI
   https://github.com/databricks/cli/issues/5022
   
