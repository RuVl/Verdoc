import {defineStore} from 'pinia';
import Product from "@/models/Product.js";

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
        addItem(product) {
            const index = this.items.findIndex(item => item.id === product.id);
            if (index !== -1) this.items[index].quantity += product.quantity;
            else this.items.push(product);
        },
        removeItem(product) {
            const index = this.items.findIndex(item => item.id === product.id);
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
                // Convert items to product instances
                parsed.items = parsed.items.map(item => new Product(item));
                return parsed;
            },
            serialize: JSON.stringify
        }
    }
});
