#!/usr/bin/env bash
# Shared by setup and post-run steps. stdout is reserved for validated API JSON.

cf_error() {
  local message="$1"
  # API error messages are untrusted workflow-command content.
  if [[ -n "${CF_API_TOKEN:-}" ]]; then
    message="${message//"$CF_API_TOKEN"/[REDACTED]}"
  fi
  message="${message//'%'/'%25'}"
  message="${message//$'\r'/'%0D'}"
  message="${message//$'\n'/'%0A'}"
  printf '::error::%s\n' "$message" >&2
}

# Usage: cf_request METHOD API_PATH RESULT_PREDICATE [JSON_BODY]
# No retries: replaying mutations can create duplicate lists/rules.
cf_request() {
  local method="$1" path="$2" predicate="$3"
  local response body status details hint
  CF_HTTP_STATUS=''
  CF_RESPONSE_BODY=''
  local -a args=(--silent --show-error --connect-timeout 15 --max-time 60
    --request "$method" --url "https://api.cloudflare.com/client/v4$path"
    --header 'Content-Type: application/json'
    --header "Authorization: Bearer ${CF_API_TOKEN:-}"
    --write-out $'\n%{http_code}')

  if [[ -z "${CF_API_TOKEN:-}" ]]; then
    cf_error 'cf_api_token is empty. Supply a Cloudflare API token, not the Global API Key.'
    return 1
  fi
  if [[ $# -eq 4 ]]; then
    args+=(--data "$4")
  fi
  case "$path" in
    /accounts/*) hint='Check cf_account_id and Account > Account Filter Lists > Edit; the token must include the target account.' ;;
    */bot_management) hint='Check cf_zone_id, Zone > Bot Management > Edit and Zone > Zone > Read, and the token zone scope.' ;;
    *) hint='Check cf_zone_id, Zone > Zone WAF > Edit, and the token zone scope.' ;;
  esac

  if ! response=$(curl "${args[@]}"); then
    cf_error "Cloudflare $method $path: network/TLS/timeout failure. The request may have reached Cloudflare; verify state before retrying."
    return 1
  fi
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
  CF_HTTP_STATUS="$status"
  CF_RESPONSE_BODY="$body"

  # Reject invalid JSON, multiple JSON values, and non-object envelopes.
  if ! jq -e -s 'length == 1 and (.[0] | type == "object")' <<< "$body" >/dev/null 2>&1; then
    cf_error "Cloudflare $method $path: HTTP $status; expected a JSON object, received an invalid response."
    return 1
  fi
  if [[ ! "$status" =~ ^2[0-9][0-9]$ ]] || ! jq -e '.success == true' <<< "$body" >/dev/null; then
    details=$(jq -r '[.errors[]? | objects | "\(.code // "unknown"): \(.message // "No message")"] | join("; ")' <<< "$body" 2>/dev/null) || details='Malformed error details'
    cf_error "Cloudflare $method $path: HTTP $status; ${details:-API did not report success}. $hint"
    return 1
  fi
  if ! jq -e "$predicate" <<< "$body" >/dev/null 2>&1; then
    cf_error "Cloudflare $method $path: HTTP $status; success response has an unexpected result shape."
    return 1
  fi
  printf '%s\n' "$body"
}

# Only this endpoint has a legitimate not-yet-created (404) state.
cf_entrypoint() {
  local output_file result
  output_file=$(mktemp) || return 1
  if cf_request GET "$1" '.result.id | type == "string" and test("^[a-fA-F0-9]{32}$")' > "$output_file" 2> "${output_file}.err"; then
    result=$(< "$output_file")
    rm -f "$output_file" "${output_file}.err"
    printf '%s\n' "$result"
  elif [[ "${CF_HTTP_STATUS:-}" == 404 ]] && jq -e -s 'length == 1 and (.[0] | type == "object" and .success == false and (.errors | type == "array" and length > 0))' <<< "${CF_RESPONSE_BODY:-}" >/dev/null 2>&1; then
    rm -f "$output_file" "${output_file}.err"
    printf '%s\n' '{"result":null}'
  else
    cat "${output_file}.err" >&2
    rm -f "$output_file" "${output_file}.err"
    return 1
  fi
}
