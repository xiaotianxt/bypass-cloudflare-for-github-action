## Unreleased

### Fixed
- Isolate list/IP/BFM state in per-invocation step outputs so post-run cleanup cannot read another invocation's job-global environment state.
- Accept SBFM/Enterprise configurations without a Free BFM field without mutating their settings. Only explicitly enabled BFM is toggled/restored; JavaScript detections are left unchanged.
- Validate HTTP status, API success, and result shape for every Cloudflare request, including cleanup and Bot Fight Mode restoration (#17).
- Report Cloudflare error codes/messages and relevant permission/resource-scope guidance instead of failing with `Cannot iterate over null`.
- Register cleanup/restoration before mutations, and stop reporting success when post-run API requests fail.
- Validate required secrets, IDs, boolean/delay inputs, and the runner IP before modifying Cloudflare state.

### Added
- Shared API request handling with bounded network requests, escaped error annotations, and no automatic mutation retries.
- Offline API regression tests and CI; updated token setup and troubleshooting documentation.
- Real GitHub runner post-lifecycle coverage using a strict offline API fixture, two independent invocations, and four bot configuration variants.

## v2.1.0

### Added
- **Bot Fight Mode (BFM) bypass support**: New `disable_bot_fight_mode` input option to temporarily disable Super Bot Fight Mode / Bot Fight Mode during workflow execution
- New `bfm_propagation_delay` input to configure wait time for BFM settings to propagate (default: 10 seconds)
- Automatic restoration of original BFM state after job completion (success or failure)

### Why this matters
Super Bot Fight Mode (SBFM) and Bot Fight Mode (BFM) [do not respect WAF skip rules](https://developers.cloudflare.com/bots/get-started/super-bot-fight-mode/). This means even with the IP whitelist and WAF bypass rule, requests from GitHub Actions runners could still be blocked. The new `disable_bot_fight_mode` option temporarily disables BFM via the [Cloudflare Bot Management API](https://developers.cloudflare.com/api/resources/bot_management/), allowing your workflows to successfully access Cloudflare-protected endpoints.

### Usage
```yaml
- uses: xiaotianxt/bypass-cloudflare-for-github-action@v2.1.0
  with:
    cf_account_id: ${{ secrets.CF_ACCOUNT_ID }}
    cf_zone_id: ${{ secrets.CF_ZONE_ID }}
    cf_api_token: ${{ secrets.CF_API_TOKEN }}
    disable_bot_fight_mode: 'true'
```

### Note
Using `disable_bot_fight_mode` requires **Zone Settings > Edit** permission on your Cloudflare API token.

---

v2.0.1