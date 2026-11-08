# PC1 health

- **backend-down** -- HTTP 502 -- the funnel is up but the winremote MCP backend (127.0.0.1:8090) is not running; only a human at PC1 can restart it
- next: At PC1, run:  ops\pc1_fix_remote.ps1 -Token <PC1_MCP_TOKEN> -Persist  (restarts the winremote MCP server so it also survives a reboot)
