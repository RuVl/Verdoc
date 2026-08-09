// A failed request must never look like nothing happening. This turns an axios error into an i18n
// key so every form says the same thing about the same failure.

// What each status means wherever it can happen. Anything context-specific (a 404 that means
// "no purchases on this address", a 502 that means "the payment gateway did not answer") is
// passed in by the caller.
const BY_STATUS = {
    400: 'errors.invalid_email',
    429: 'errors.too_often',
};

export function errorMessageKey(error, overrides = {}) {
    const status = error.response?.status;

    // No response at all: the backend is down, the request timed out, or the browser is offline.
    if (status === undefined)
        return 'errors.network';

    return overrides[status] ?? BY_STATUS[status] ?? 'errors.unavailable';
}
