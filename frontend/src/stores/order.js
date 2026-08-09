import {defineStore} from 'pinia';
import plisio_icon from "@/assets/plisio.png";
import {useCartStore} from "@/stores/cart";
import {useSettingsStore} from "@/stores/settings";
import apiClient from "@/api/index.js";

export const useOrderStore = defineStore('order', {
    state: () => ({
        payment_methods: [
            {name: 'plisio', icon: plisio_icon}
        ],
    }),
    actions: {
        // Both ways of buying are the same request; the error is deliberately not caught here, the
        // form that started it is the only place that can tell the customer about it.
        async _checkout(email, items) {
            const response = await apiClient.post('/order/', {
                email: email,
                // Remembered on the Customer: the delivery e-mail is sent from the payment
                // webhook, long after this browser is gone.
                language: useSettingsStore().currentLanguage,
                items: items,
            });

            return response.data.redirect_url;
        },
        async makeOrder(email) {
            const cartStore = useCartStore();
            const items = cartStore.cartItems.map(item => ({
                product_id: item.id,
                quantity: item.quantity,
            }));

            const redirect_url = await this._checkout(email, items);
            // Only once the invoice exists: a failed checkout must leave the cart alone.
            cartStore.clearCart();
            window.location.href = redirect_url;
        },
        async buyProduct(product, email) {
            window.location.href = await this._checkout(email, [{
                product_id: product.id,
                quantity: product.quantity,
            }]);
        }
    }
});
