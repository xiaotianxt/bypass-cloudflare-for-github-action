<h1 align='center'>
<samp>Bypass Cloudflare for GitHub Action</samp>
</h1>
<p align='center'>
  <samp>Never receive 403 Forbidden from Cloudflare again.</samp>
</p>

Requests from GitHub Action servers to a Cloudflare proxied host may be blocked by [Cloudflare's Web Application Firewall(WAF)](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/) or [Bot Fight Mode](https://developers.cloudflare.com/bots/get-started/free/).
This action automatically manages IP whitelisting by creating a Cloudflare custom IP list and WAF rule to bypass Cloudflare protections for GitHub Actions runners.

## Features
- Automatically retrieves the public IP of the GitHub Action runner.
- Checks if a Cloudflare custom IP list exists, creating it if needed.
- Creates a custom WAF rule to bypass Cloudflare protections for IPs in the list (only on first setup).
- Adds the runner's IP to the Cloudflare IP list.
- Automatically cleans up by removing the IP from the list after the job completes.

## Inputs
| Input            | Description                | Required |
| ---------------- | -------------------------- | -------- |
| `cf_account_id`  | Cloudflare Account ID      | true     |
| `cf_zone_id`     | Cloudflare Zone ID         | true     |
| `cf_api_token`   | Cloudflare API Token       | true     |

## Usage
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
        uses: xiaotianxt/bypass-cloudflare-for-github-action@v1.1.1
        with:
          cf_account_id: ${{ secrets.CF_ACCOUNT_ID }}
          cf_zone_id: ${{ secrets.CF_ZONE_ID }}
          cf_api_token: ${{ secrets.CF_API_TOKEN }}
      - name: Send request to Cloudflare-protected server
        run: curl https://example.com/api
```

## Set Repo Secrets
Remember to add your Cloudflare Account ID, Zone ID, and API Token to your GitHub repository > Secrets and Variables > Actions as `CF_ACCOUNT_ID`, `CF_ZONE_ID`, and `CF_API_TOKEN` respectively.

This Action requires a Cloudflare API Token, not the Global API Key. To create an API token:

1. Log in to the Cloudflare dashboard and click into an account.
2. On the right sidebar, go to "API" > "Get your API token".
3. Click "Account API Tokens" > "Create Token" > "Create Custom Token".
4. Create a custom token with the following permissions:
   - **Account** > **Account Filter Lists** > **Edit** (required for IP list management)
   - **Zone** > **Zone WAF** > **Edit** (required for custom WAF rules)
5. Set the token to access the zone you're working with.
6. Create the token and save it securely.

> **Important:** The first time this workflow runs, the Custom WAF Rule is created. After the first run, you can remove the `Zone WAF > Edit` permission from the API token.

## Limitations

- Cloudflare Free plan allows only **one custom IP list** per zone. If you already use a custom list, this action cannot create an additional one. [Learn more](https://developers.cloudflare.com/waf/tools/lists/#limits).
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
