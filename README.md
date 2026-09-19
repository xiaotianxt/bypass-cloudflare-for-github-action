<h1 align='center'>
<samp>Bypass Cloudflare for GitHub Action</samp>
</h1>
<p align='center'>
  <samp>Never receive 403 Forbidden from Cloudflare again.</samp>
</p>

> [!NOTE]
> Version `v2.0.0` addresses Cloudflare API changes affecting Free plan users. It includes breaking changes, such as updated API token permissions. If you are on a paid Cloudflare plan and the old workflow still works for you, continue using `v1.1.1`.

Requests from GitHub Action servers to a Cloudflare proxied host may be blocked by [Cloudflare's Web Application Firewall(WAF)](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/) or [Bot Fight Mode](https://developers.cloudflare.com/bots/get-started/free/).
This action automatically manages IP whitelisting by creating a Cloudflare custom IP list and WAF rule to bypass Cloudflare protections for GitHub Actions runners.

## Features
- Automatically retrieves the public IP of the GitHub Action runner.
- Checks if a Cloudflare custom IP list exists, creating it if needed.
- Creates a custom WAF rule to bypass Cloudflare protections for IPs in the list (only on first setup).
- Adds the runner's IP to the Cloudflare IP list.
- Automatically cleans up by removing the IP from the list after the job completes.

## Inputs
| Input                    | Description                                                                                      | Required | Default |
| ------------------------ | ------------------------------------------------------------------------------------------------ | -------- | ------- |
| `cf_account_id`          | Cloudflare Account ID                                                                            | true     |         |
| `cf_zone_id`             | Cloudflare Zone ID                                                                               | true     |         |
| `cf_api_token`           | Cloudflare API Token                                                                             | true     |         |
| `disable_bot_fight_mode` | Disable Bot Fight Mode during workflow execution (requires Bot Management > Edit and Zone > Read permissions) | false    | `false` |
| `bfm_propagation_delay`  | Seconds to wait after disabling Bot Fight Mode for settings to propagate                         | false    | `10`     |

## Usage
The runner needs Bash, curl, jq, and Python 3 (for IPv4/IPv6 validation), available on GitHub-hosted Ubuntu runners.

To use this action, create a workflow in your repository's `.github/workflows` directory. Below is an example workflow file:

```yaml
name: Bypass Cloudflare for API Access
on: [push]
jobs:
  manage-ip-whitelist:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
      - name: Bypass Cloudflare for GitHub Action
        uses: xiaotianxt/bypass-cloudflare-for-github-action@v2.1.0
        with:
          cf_account_id: ${{ secrets.CF_ACCOUNT_ID }}
          cf_zone_id: ${{ secrets.CF_ZONE_ID }}
          cf_api_token: ${{ secrets.CF_API_TOKEN }}
      - name: Send request to Cloudflare-protected server
        run: curl https://example.com/api
```

### With Bot Fight Mode Bypass

If you have [Super Bot Fight Mode (SBFM) or Bot Fight Mode (BFM)](https://developers.cloudflare.com/bots/get-started/super-bot-fight-mode/) enabled, WAF rules alone may not be sufficient as these modes [do not respect WAF skip rules](https://developers.cloudflare.com/bots/get-started/super-bot-fight-mode/). Use the `disable_bot_fight_mode` option to temporarily disable BFM during your workflow:

```yaml
name: Bypass Cloudflare with BFM Disabled
on: [push]
jobs:
  manage-ip-whitelist:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
      - name: Bypass Cloudflare for GitHub Action
        uses: xiaotianxt/bypass-cloudflare-for-github-action@v2.1.0
        with:
          cf_account_id: ${{ secrets.CF_ACCOUNT_ID }}
          cf_zone_id: ${{ secrets.CF_ZONE_ID }}
          cf_api_token: ${{ secrets.CF_API_TOKEN }}
          disable_bot_fight_mode: 'true'
      - name: Send request to Cloudflare-protected server
        run: curl https://example.com/api
```

> [!NOTE]
> The `disable_bot_fight_mode` option requires **Bot Management > Edit** and **Zone > Read** permissions on your API token (the endpoint used is `/zones/{zone_id}/bot_management`). The original BFM state is automatically restored after the job completes.

## Set Repo Secrets
Remember to add your Cloudflare Account ID, Zone ID, and API Token to your GitHub repository > Secrets and Variables > Actions as `CF_ACCOUNT_ID`, `CF_ZONE_ID`, and `CF_API_TOKEN` respectively.

This Action requires a Cloudflare API Token, not the Global API Key. To create an API token:

1. Log in to the Cloudflare dashboard.
2. Open [My Profile > API Tokens](https://dash.cloudflare.com/profile/api-tokens) to create a user API token. Account-owned API tokens may also be used if available for your account.
3. Click **Create Token** > **Create Custom Token**. Dashboard navigation can vary; the permissions and resource scopes below are what matter.
4. Create a custom token with the following permissions:
   - **Account** > **Account Filter Lists** > **Edit** (required for IP list management)
   - **Zone** > **Zone WAF** > **Edit** (required for custom WAF rules)
   - **Zone** > **Bot Management** > **Edit** (required only if using `disable_bot_fight_mode`)
   - **Zone** > **Zone** > **Read** (required only if using `disable_bot_fight_mode`)
5. Include the **account matching `cf_account_id`** in the token's account resources, and the **zone matching `cf_zone_id`** in its zone resources. Lists are account-level resources: zone permissions alone are not sufficient.
6. Create the token and save it securely.

> [!IMPORTANT]
> The first time this workflow runs, the Custom WAF Rule is created. After the first run, you can remove the `Zone WAF > Edit` permission from the API token.

## Troubleshooting

Cloudflare requests validate the HTTP status, API `success` flag, and expected result before reading fields. Failures include the operation, HTTP status, Cloudflare error code/message (when available), and relevant permission/scope guidance. For example:

```text
Cloudflare GET /accounts/.../rules/lists: HTTP 403; 10000: Authentication error. Check cf_account_id and Account > Account Filter Lists > Edit; the token must include the target account.
```

- **Empty inputs / invalid IDs:** check Actions secrets and confirm Account ID and Zone ID are not swapped. Secrets may be unavailable to workflows from fork pull requests.
- **Authentication or authorization failures:** use an API token, not the Global API Key; check expiry, permissions, account/zone scope, and any token client-IP restrictions. An authentication error alone does not identify which of these is wrong. [Lists API permissions](https://developers.cloudflare.com/api/resources/rules/subresources/lists/methods/list/).
- **Non-JSON or malformed responses:** the action reports an invalid response rather than a misleading jq failure. Check Cloudflare service status and runner proxy/network configuration.
- **Network/timeout failures:** requests are bounded and mutations are not automatically retried. A timed-out request may already have reached Cloudflare; inspect the resource state before rerunning.
- **Cleanup/restoration failures:** post-run steps report API failures and fail instead of claiming success. Check the IP list and original Bot Fight Mode settings manually if cleanup fails or the runner is terminated before post-run steps can execute.

If reporting an issue, include the failing step and sanitized error annotation, plus the action version. Never share API tokens or Authorization headers.

## Development

Offline regression tests use synthetic API responses and do not require Cloudflare credentials:

```bash
python3 -m pip install 'PyYAML==6.0.2'
python3 -m unittest discover -s tests -v
shellcheck scripts/cloudflare.sh
```

## Limitations

- IP list writes are asynchronous. An accepted operation does not guarantee that the list has propagated yet; this action does not currently poll operation completion.
- The action replaces and clears a shared list, and optionally changes zone-wide Bot Fight Mode settings. Do not run overlapping jobs against the same resources; use workflow concurrency controls (and coordinate across repositories).
- Initial list and WAF rule creation is not transactional. If rule creation fails after the list is created, repair the WAF rule before rerunning; an existing list does not prove setup completed.
- Cloudflare Free plan allows only **one custom IP list** per account. If you already use a custom list, this action cannot create an additional one. [Learn more](https://developers.cloudflare.com/waf/tools/lists/#limits).
- Cloudflare Free plan allows only **five custom WAF rules** per zone. If you are already at the quota, the initial setup step that creates the bypass rule will fail. [Learn more](https://developers.cloudflare.com/waf/custom-rules/limits/).

## How It Works

1. **First Run (Setup)**: 
   - Checks if the IP list `bypass_cloudflare_for_github_action_list` exists
   - If not found, creates the IP list and a custom WAF rule that skips Cloudflare protections for IPs in the list
   - Adds the runner's IP to the list

2. **Subsequent Runs**:
   - Reuses the existing IP list
   - Adds the runner's IP to the list

3. **Cleanup**:
   - After the job completes (success or failure), automatically removes the runner's IP from the list
   - If `disable_bot_fight_mode` was enabled, restores the original Bot Fight Mode settings
