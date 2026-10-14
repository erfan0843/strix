/* Server-only integration policy for the Nora UI scaffold.
 * No provider SDK, outbound request, token parsing, queue write, or message send lives here.
 */
export const DELIVERY_POLICY = Object.freeze({
  certificate: Object.freeze(['bale']),
  ticket: Object.freeze(['bale']),
  notification: Object.freeze(['bale', 'eitaa'])
});

// Both integrations belong to the same application deployment. Bale uses the
// app server's bot token plus its Mini App; Eitaa is represented as Mini App
// only in this scaffold (no separate Eitaa bot-token field is defined).
export const PROVIDER_MODES = Object.freeze({
  bale: Object.freeze({ connectionModel: 'bot-token-plus-mini-app', credentialScope: 'same-application-server' }),
  eitaa: Object.freeze({ connectionModel: 'mini-app-only', credentialScope: 'none-in-this-scaffold' })
});

const KINDS = new Set(Object.keys(DELIVERY_POLICY));
const FORMATS = new Set(['pdf', 'jpg']);
const SECRET_FIELD = /token|secret|authorization|api[_-]?key|password|credential/i;

function containsSecretField(value, depth = 0) {
  if (!value || typeof value !== 'object' || depth > 12) return false;
  for (const [key, child] of Object.entries(value)) {
    if (SECRET_FIELD.test(key) || containsSecretField(child, depth + 1)) return true;
  }
  return false;
}

export function validateOutboxRequest(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ok: false, status: 400, code: 'invalid_json_object' };
  }
  if (containsSecretField(value)) {
    return { ok: false, status: 400, code: 'credentials_not_accepted' };
  }

  const kind = String(value.kind || '');
  const channel = String(value.channel || '');
  if (!KINDS.has(kind)) return { ok: false, status: 400, code: 'unsupported_kind' };
  if (!DELIVERY_POLICY[kind].includes(channel)) {
    return { ok: false, status: 400, code: 'channel_not_allowed' };
  }

  let format = '';
  if (kind === 'certificate' || kind === 'ticket') {
    format = String(value.format || 'pdf').toLowerCase();
    if (!FORMATS.has(format)) return { ok: false, status: 400, code: 'unsupported_format' };
  }

  return { ok: true, request: Object.freeze({ kind, channel, format }) };
}

export function publicIntegrationStatus() {
  // Deliberately do not inspect or return environment variables or credential presence.
  return {
    mode: 'server-scaffold',
    deliveryEnabled: false,
    queueEnabled: false,
    sendAttempted: false,
    serverScope: 'same-application',
    secretHandling: 'same-application-server-only; values and presence are not exposed',
    providers: [
      { id: 'bale', name: 'بله', ...PROVIDER_MODES.bale, connected: false, state: 'not_connected' },
      { id: 'eitaa', name: 'ایتا', ...PROVIDER_MODES.eitaa, connected: false, state: 'mini_app_not_connected' }
    ],
    policy: {
      certificate: [...DELIVERY_POLICY.certificate],
      ticket: [...DELIVERY_POLICY.ticket],
      notification: [...DELIVERY_POLICY.notification]
    },
    ownerApproval: 'requires_server_verified_approval'
  };
}

export function dispatchOutbox(preparedRequest) {
  // This hard stop is intentionally not controlled by browser state or env flags.
  return {
    accepted: false,
    queued: false,
    dispatched: false,
    sendAttempted: false,
    reason: 'server_approval_and_provider_adapter_not_configured',
    channel: preparedRequest && preparedRequest.channel || ''
  };
}
