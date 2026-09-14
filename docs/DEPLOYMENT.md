# Judge test build and deployment status

**No AWS deployment exists in this release.** Temporary AWS login, STS and the Bedrock model catalog succeeded. AWS denied the first model request because the new account is still being verified. Successful model access and any hosting endpoint remain unverified. The working fallback is the reproducible local server.

```sh
uv sync --frozen --python 3.12
uv run --no-sync python -m prizehunter_aws.web --port 8080
```

Open http://127.0.0.1:8080/ and follow the README. `/health` returns status `ok` and `paid_browser_calls: false`. Stop the terminal process with Ctrl-C. The browser cannot invoke a model, arbitrary URL or filesystem path. State persists in `local-state/web`; use the dedicated first-observation/reset button for a fresh demonstration.

The server is a local test build, not a production web server or deployed AWS service. There is no hosting URL, AgentCore, Cognito, scheduler or external notification service. The current architecture diagram only includes verified components.

Once AWS account verification and real analysis succeed, choose a single minimal AWS server-side host, retain server-side credentials, curated requests and bounded costs, and verify the actual endpoint before changing this status. This is a pending operational step, not infrastructure that has already been implemented. The user's sprint budget is under USD 10; an operator must account for both inference and hosting and stop/clean up only the resources created for that deployment.
