import axios from 'axios';

export default axios.create({
	baseURL: __API_URL__,
	timeout: 10000,
	headers: {
		'Content-Type': 'application/json',
		'Accept': 'application/json',
	},
	withXSRFToken: true,
	xsrfHeaderName: 'X-CSRFTOKEN',
	xsrfCookieName: 'csrftoken',
});
