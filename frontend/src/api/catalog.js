import api from '@/api/index.js';
import Country from '@/models/Country.js';

// The storefront is one call: countries with their products nested. Models are built here rather
// than in the view, so a change to the payload is a change to this file alone.
export async function fetchCountries() {
    const response = await api.get('/countries/');
    return response.data.map(country => Country.fromApi(country));
}

// Rates for the client-side currency switch. Prices on the purchases page are never run through
// it - those are what was actually charged.
export async function fetchExchangeRates() {
    const response = await api.get('/exchange-rates/');
    return response.data;
}
