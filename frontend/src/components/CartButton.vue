<script setup>
import CartIcon from "@/components/icons/IconCart.vue";
import CircleCounter from "@/components/CircleCounter.vue";
import {useCartStore} from "@/stores/cart.js";
import {storeToRefs} from "pinia";

const cartStore = useCartStore();
const {cartItemCount} = storeToRefs(cartStore);
</script>

<template>
  <router-link class="cart-btn-wrapper" :to="{name: 'cart'}">
    <CartIcon size="small"/>
    <span>{{$t('buttons.cart')}}</span>
    <CircleCounter v-if="cartItemCount > 0" :count="cartItemCount"/>
  </router-link>
</template>

<style scoped>
.cart-btn-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;

  color: var(--accent-color);
  font-weight: 600;
  font-size: 16px;
  text-decoration: none;

  &:hover {
    opacity: .9;
  }
}
</style>