<script setup>
import {ref} from "vue";
import {storeToRefs} from "pinia";
import {useCartStore} from "@/stores/cart.js";
import {useCurrenciesStore} from "@/stores/currencies.js";
import CountryFlag from 'vue-country-flag-next';
import ViewBlock from "@/components/ViewBlock.vue";
import ListView from "@/components/ListView.vue";
import TrashIcon from "@/components/icons/IconTrash.vue";
import CommonButton from "@/components/CommonButton.vue";
import QuantityChanger from "@/components/CounterChanger.vue";
import SelectPayment from "@/components/SelectPayment.vue";

const cartStore = useCartStore();
const {cartItems, cartItemCount, totalPrice} = storeToRefs(cartStore);

const currencyStore = useCurrenciesStore();
const {currentCurrency} = storeToRefs(currencyStore);

const is_opened = ref(false);
</script>

<template>
  <ViewBlock class="cart-view">
    <template #title>{{ $t('routes.cart') }}</template>
    <div v-if="cartItemCount === 0" class="empty-cart">
      {{ $t('cart_view.empty') }}
    </div>
    <div v-else>
      <ListView v-slot="{element: item, index: i}" :elements="cartItems" class="cart-item">
        <div class="item-head">
          <CountryFlag :country="item.code" class="flag-icon"/>
          <span class="product-name">{{ item.name }}</span>
        </div>
        <QuantityChanger v-model:item="cartItems[i]" counter_name="quantity"/>
        <div class="cost-block">
          <span class="cost-label short">{{ $t('cart_view.cost') }}:</span>
          <span class="cost-label full">{{ $t('cart_view.cost_full') }}:</span>
          <span class="product-cost">{{ item.formattedPrice() }}</span>
        </div>
        <button class="remove-btn" @click="cartStore.removeItem(item)">
          <span class="remove-label">{{ $t('buttons.delete') }}</span>
          <TrashIcon/>
        </button>
      </ListView>
      <hr>
      <div class="total-price-block">
        <div>
          <span>{{ $t('cart_view.total') }}:</span>
          <span class="total-price">{{ totalPrice.toFixed(2) }} {{ currentCurrency.sign }}</span>
        </div>
        <CommonButton tabindex="0" @click="is_opened=true">
          {{ $t('buttons.payment_method') }}
        </CommonButton>
        <SelectPayment v-model:is_opened="is_opened"/>
      </div>
    </div>
  </ViewBlock>
</template>

<style lang="scss" scoped>
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
      min-width: $height;
      background-position-x: calc(($height - $width) / 2);
      background-repeat: no-repeat;

      margin-bottom: 0;
    }

    // flag + name stay grouped on one line; on desktop the group fills the free space
    .item-head {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      min-width: 0;
    }

    .product-name {
      flex: 1;
      min-width: 0;
      // robustly override the `text-wrap: nowrap` inherited from ListView's li;
      // white-space is universally supported, unlike `text-wrap: pretty` alone
      white-space: normal;
      overflow-wrap: anywhere;
      text-wrap: pretty; // progressive enhancement for nicer line breaks
    }

    .product-cost {
      display: inline-block;
      text-align: center;
      min-width: 100px;
      padding: 10px 0;
      background-color: var(--second-color);
      border-radius: 10px;
    }

    .cost-block {
      & > span {
        margin: 0 10px;
      }

      .cost-label.full {
        display: none; // full label is shown only on the mobile card
      }
    }

    .remove-btn {
      border: 0;
      background-color: var(--red-color);
      border-radius: 5px;
      cursor: pointer;
      height: 27px;
      min-width: 27px;
      line-height: 0;

      .remove-label {
        display: none; // text label is shown only on the mobile card
      }

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

@media screen and (max-width: 768px) {
  .cart-view {
    // stack the row into a centered card; dashed divider between items
    :deep(.products-list > ul > li) {
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 12px;
      padding: 20px 0;
      border-bottom: 1px dashed var(--second-color);
    }

    .cart-item {
      .item-head {
        flex: 0 0 auto;
        justify-content: center;
        max-width: 100%;
      }

      .cost-block {
        display: flex;
        align-items: center;
        justify-content: center;

        .cost-label.short {
          display: none;
        }

        .cost-label.full {
          display: inline;
        }
      }

      // plain bold price, no chip - matches the mockup
      .product-cost {
        min-width: 0;
        padding: 0;
        background: none;
        font-weight: 700;
      }

      .remove-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: auto;
        height: auto;
        padding: 8px 18px;
        color: #ffffff;
        font-weight: 600;
        line-height: 1;

        .remove-label {
          display: inline;
        }
      }
    }

    // stack the pay button under the sum so they never collide on narrow screens
    .total-price-block {
      flex-direction: column;
      align-items: stretch;
      gap: 20px;

      > div {
        flex-direction: row;
        align-items: baseline;
        justify-content: space-between;
      }
    }
  }
}
</style>
