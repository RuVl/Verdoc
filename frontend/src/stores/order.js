import {defineStore} from 'pinia';
import plisio_icon from "@/assets/plisio.png";
import {useCartStore} from "@/stores/cart";
import apiClient from "@/api/index.js";

export const useOrderStore = defineStore('order', {
	state: () => ({
		payment_methods: [
			{name: 'plisio', icon: plisio_icon}
		],
	}),
	actions: {
		async makeOrder(email) {
			const cartStore = useCartStore();
			const items = cartStore.cartItems.map(item => ({
				passport_id: item.id,
				quantity: item.quantity,
			}));

			try {
				const response = await apiClient.post('/order/', {
					user_email: email,
					items: items,
				});
				cartStore.clearCart();
				window.location.href = response.data.redirect_url;
			} catch (error) {
				console.error('Error creating order:', error);
			}
		},
		async buyPassport(passport, email) {
			try {
				const response = await apiClient.post('/order/', {
					user_email: email,
					items: [{
						passport_id: passport.id,
						quantity: passport.quantity,
					}],
				});
				window.location.href = response.data.redirect_url;
			} catch (error) {
				console.error('Error creating order:', error);
			}
		}
	}
});
