<script setup>
import CountryFlag from 'vue-country-flag-next';
import ViewBlock from "@/components/ViewBlock.vue";
import ListView from "@/components/ListView.vue";
import TrashIcon from "@/components/icons/IconTrash.vue";
import CommonButton from "@/components/CommonButton.vue";
import {useCartStore} from "@/stores/cart.js";
import {storeToRefs} from "pinia";
import {useCurrenciesStore} from "@/stores/currencies.js";

const cartStore = useCartStore();
const {cartItems, cartItemCount, totalPrice} = storeToRefs(cartStore);

const currencyStore = useCurrenciesStore();
const {currentCurrency} = storeToRefs(currencyStore);
</script>

<template>
  <ViewBlock class="cart-view">
    <template #title>{{ $t('routes.cart') }}</template>
    <div v-if="cartItemCount === 0" class="empty-cart">
      {{ $t('cart_view.empty') }}
    </div>
    <div v-else>
      <ListView class="cart-item" :elements="cartItems" v-slot="{element: item}">
        <CountryFlag class="flag-icon" :country="item.code"/>
        <span class="product-name">{{ item.name }}</span>
        <div class="quantity-block">
          <button @click="cartStore.decreaseCount(item)" :disabled="item.quantity <= 1">–</button>
          <span class="product-quantity">{{ item.quantity }} {{ $t('products.count') }}</span>
          <button @click="cartStore.increaseCount(item)" :disabled="item.quantity >= item.max_quantity">+</button>
        </div>
        <div class="cost-block">
          <span>Стоимость:</span>
          <span class="product-cost">{{ item.formattedPrice }}</span>
        </div>
        <button class="remove-btn" @click="cartStore.removeItem(item)">
          <TrashIcon/>
        </button>
      </ListView>
      <hr>
      <div class="total-price-block">
        <div>
          <span>{{ $t('cart_view.total') }}:</span>
          <span class="total-price">{{ totalPrice }} {{ currentCurrency.sign }}</span>
        </div>
        <CommonButton tabindex="0">{{ $t('buttons.payment_method') }}</CommonButton>
      </div>
    </div>
  </ViewBlock>
</template>

<style scoped lang="scss">
.cart-view {
  padding-bottom: 25px;

  .empty-cart {
    text-align: center;
    padding: 75px 0;
    margin-bottom: 25px;
    font-weight: 500;
    font-size: 16px;
  }

  .cart-item {
    .flag-icon {
      $height: 39px;
      $width: 52px;

      border-radius: 100%;
      width: $height;
      background-position-x: calc(($height - $width) / 2);
      background-repeat: no-repeat;

      margin-bottom: 0;
    }

    .product-name {
      text-wrap: pretty;
      width: 635px;
      margin-right: 20px;
    }

    .product-cost, .product-quantity {
      display: inline-block;
      text-align: center;
      min-width: 100px;
      padding: 10px 0;
      background-color: var(--second-color);
      border-radius: 10px;
    }

    .quantity-block > button {
      background: none;
      border: 0;
      font-weight: 600;
      font-size: 24px;
      margin: 10px;
      cursor: pointer;

      &:hover, &:disabled {
        opacity: .7;
      }
    }

    .cost-block {
      & > span {
        margin: 0 10px;
      }
    }

    .remove-btn {
      border: 0;
      background-color: #e4102c;
      border-radius: 5px;
      cursor: pointer;
      height: 27px;
      min-width: 27px;
      line-height: 0;

      &:hover {
        opacity: .7;
      }

      svg {
        display: inline-block;
        place-content: center;
        color: #ffffff;
        width: 20px;
        height: 20px;
      }
    }
  }

  hr {
    margin: 65px 0 15px;
    border: 0;
    border-top: 1px solid var(--second-color);
  }

  .total-price-block {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 14px;

    > div {
      display: flex;
      gap: 15px;
      flex-direction: column;
      font-size: 12px;
      font-weight: 500;
    }

    .total-price {
      font-size: 24px;
      font-weight: 600;
    }
  }
}
</style>
