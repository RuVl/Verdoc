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
		findItem(passport) {
			return this.items.find(item => item.id === passport.id);
		},
		addItem(passport) {
			const existingItem = this.findItem(passport);
			if (existingItem) this.increaseCount(passport);
			else {
				passport.quantity = 1;
				this.items.push(passport);
			}
		},
		increaseCount(passport) {
			const item = this.findItem(passport);
			if (item && item.quantity < item.max_quantity)
				item.quantity += 1;
		},
		decreaseCount(passport) {
			const item = this.findItem(passport);
			if (item && item.quantity > 1)
				item.quantity -= 1;
		},
		removeItem(passport) {
			this.items = this.items.filter(item => item.id !== passport.id);
		},
		clearCart() {
			this.items = [];
		}
	},
	persist: {
		debug: true,
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
