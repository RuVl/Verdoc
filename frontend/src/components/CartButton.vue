<script setup>
import CartIcon from "@/components/icons/IconCart.vue";
import CircleCounter from "@/components/CircleCounter.vue";
import {ref} from "vue";

const counter = ref(2);
</script>

<template>
  <router-link class="cart-btn-wrapper" :to="{name: 'cart'}">
    <CartIcon size="small"/>
    <span>Корзина</span>
    <CircleCounter :count="counter"/>
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