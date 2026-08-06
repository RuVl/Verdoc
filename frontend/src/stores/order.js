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
        async makeOrder(email) {
            console.log(`Buy all products in cart for ${email}`);

            const cartStore = useCartStore();
            const items = cartStore.cartItems.map(item => ({
                product_id: item.id,
                quantity: item.quantity,
            }));

            try {
                const response = await apiClient.post('/order/', {
                    email: email,
                    // Remembered on the Customer: the delivery e-mail is sent from the payment
                    // webhook, long after this browser is gone.
                    language: useSettingsStore().currentLanguage,
                    items: items,
                });
                cartStore.clearCart();
                window.location.href = response.data.redirect_url;
            } catch (error) {
                console.error('Error creating order:', error);
            }
        },
        async buyProduct(product, email) {
            console.log(`Buy product ${product.name} for ${email}`);

            try {
                const response = await apiClient.post('/order/', {
                    email: email,
                    language: useSettingsStore().currentLanguage,
                    items: [{
                        product_id: product.id,
                        quantity: product.quantity,
                    }],
                });
                window.location.href = response.data.redirect_url;
            } catch (error) {
                console.error('Error creating order:', error);
            }
        }
    }
});
