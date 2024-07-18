<h1 align='center'>
<samp>Bypass Cloudflare for GitHub Action</samp>
</h1>

<p align='center'>
  <samp>Never receive 403 Forbidden from Cloudflare again.</samp>
</p>

Requests from github action server to a Cloudflare proxied host may be blocked by [Cloudflare's Web Application Firewall(WAF)](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/) or [Bot Fight Mode](https://developers.cloudflare.com/bots/get-started/free/).

This action automatically adds the public IP of the GitHub Action runner to Cloudflare's firewall [IP Access rules](https://developers.cloudflare.com/waf/tools/ip-access-rules/).

## Features

- Automatically retrieves the public IP of the GitHub Action runner.
- Adds the runner's IP to Cloudflare's firewall access rules.
- Waits for the IP to appear in Cloudflare's access rules.
- Cleans up by removing the IP from Cloudflare's access rules after the job is complete.

## Inputs

| Input        | Description        | Required |
| ------------ | ------------------ | -------- |
| `cf_zone_id` | Cloudflare Zone ID | true     |
| `cf_api_key` | Cloudflare API Key | true     |

## Outputs

| Output    | Description                       |
| --------- | --------------------------------- |
| `rule_id` | The ID of the created access rule |

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
        uses: actions/checkout@v2

      - name: Bypass Cloudflare for GitHub Action
        uses: xiaotianxt/bypass-cloudflare-for-github-action@v1.0.0
        with:
          cf_zone_id: ${{ secrets.CF_ZONE_ID }}
          cf_api_key: ${{ secrets.CF_API_KEY }}

      - name: Send request to Cloudflare-protected server
        run: curl https://example.com/api
