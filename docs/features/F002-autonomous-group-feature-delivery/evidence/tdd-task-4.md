# F002 TDD Evidence - Task 4 Mandatory Feature MCP

## Red

`python -m unittest tests.test_feature_mcp -v` failed at import because
`server.mcp_servers.feature` did not exist. The tests already bind the intended
contract: mandatory core selection even with no optional MCPs, status without
dispatch consumption, mutation headers with both Session and dispatch
capabilities, secret-free errors, and secrets present only in child env rather
than Claude/Codex argv or MCP configuration.

## Green

`python -m unittest tests.test_feature_mcp tests.test_feature_routes -v`
passes 11 tests. Feature MCP is mandatory for both harnesses, mutation headers
bind the Session and exact dispatch, and capabilities remain absent from
provider argv/config while present in the assigned child environment.
