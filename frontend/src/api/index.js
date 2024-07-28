import axios from 'axios';

const apiClient = axios.create({
	baseURL: 'https://verif-docs.com/api',
	timeout: 10000,
	headers: {
		'Content-Type': 'application/json',
		Accept: 'application/json',
	},
});

export default apiClient;
