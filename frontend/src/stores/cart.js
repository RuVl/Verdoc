import {defineStore} from 'pinia';
import Passport from "@/models/Passport.js";

export const useCartStore = defineStore('cart', {
	state: () => ({
		items: [],
	}),
	getters: {
		cartItems: state => state.items,
		cartItemCount: state => state.items.length,
		totalPrice: state => state.items.reduce((total, item) => total + item.amount * item.quantity, 0)
	},
	actions: {
		addItem(passport) {
			const index = this.items.findIndex(item => item.id === passport.id);
			if (index !== -1) this.items[index].quantity += passport.quantity;
			else this.items.push(passport);
		},
		removeItem(passport) {
			const index = this.items.findIndex(item => item.id === passport.id);
			if (index !== -1) this.items.splice(index, 1);
		},
		clearCart() {
			this.items = [];
		}
	},
	persist: {
		serializer: {
			deserialize: (s) => {
				const parsed = JSON.parse(s);
				// Convert items to passport instances
				parsed.items = parsed.items.map(item => new Passport(item));
				return parsed;
			},
			serialize: JSON.stringify
		}
	}
});
