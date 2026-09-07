import api from '@/api/index.js';

// Reading the token changes nothing - mail scanners pre-fetch every URL in a message, and a
// customer who opens the link out of curiosity must not lose the list. Only unsubscribe() opts out.
export async function readUnsubscribeToken(token) {
    const response = await api.get(`/unsubscribe/${token}/`);
    return response.data;
}

export async function unsubscribe(token) {
    const response = await api.post(`/unsubscribe/${token}/`);
    return response.data;
}
