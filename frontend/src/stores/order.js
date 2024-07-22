import {defineStore} from 'pinia';
import plisio_icon from "@/assets/plisio.png";

export const useOrderStore = defineStore('order', {
	state: () => ({
		payment_methods: [
			{name: 'plisio', icon: plisio_icon}
		],
	}),
	actions: {
		makeOrder() {
			alert('TODO');
		},
		buyPassport(passport) {
			alert('TODO');
		}
	}
});
