import api from '@/api/index.js';

// The checkout waits on Plisio, and the backend gives that call 30 seconds. The client has to
// outlast the server or a working invoice reads as a dead network: the order exists, the customer
// is told nothing happened. Everything else keeps the 10s default from api/index.js.
export const CHECKOUT_TIMEOUT_MS = 40000;

// The error is deliberately not caught here - the form that started the request is the only place
// that can tell the customer what went wrong.
export async function checkout({email, language, items}) {
    const response = await api.post('/order/', {email, language, items}, {timeout: CHECKOUT_TIMEOUT_MS});
    return response.data.redirect_url;
}

export async function fetchPurchases(token) {
    const response = await api.get(`/purchases/${token}/`);
    return response.data;
}

export async function refreshAllocation(token, allocationId) {
    const response = await api.post(`/purchases/${token}/refresh/${allocationId}/`);
    return response.data;
}

export async function refreshAllAllocations(token) {
    const response = await api.post(`/purchases/${token}/refresh-all/`);
    return response.data;
}

// The recovery path for a lost link: tops up anything undelivered and mails a fresh page token.
export async function sendPurchasesLink({email, language}) {
    return api.post('/send-links/', {email, language});
}
