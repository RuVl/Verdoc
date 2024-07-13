<script setup>
import {ref, computed} from 'vue';
import CountryFlag from 'vue-country-flag-next';
import ViewBlock from "@/components/ViewBlock.vue";
import ListView from "@/components/ListView.vue";
import TrashIcon from "@/components/icons/IconTrash.vue";
import CommonButton from "@/components/CommonButton.vue";

const cartItems = ref([
  {
    id: 1,
    flag: 'au',
    name: 'Австралия Паспорт скан',
    quantity: 24,
    price: 123
  },
  {
    id: 2,
    flag: 'au',
    name: 'Австралия DL фото с одной стороны',
    quantity: 24,
    price: 123
  }
]);

const currency_symbol = ref('₽');

const removeFromCart = (id) => {
  cartItems.value = cartItems.value.filter(item => item.id !== id);
};

const totalPrice = computed(() => {
  return cartItems.value.reduce((acc, item) => acc + item.price, 0).toFixed(2);
});
</script>

<template>
  <ViewBlock class="cart-view">
    <template #title>Корзина</template>
    <div v-if="cartItems.length === 0" class="empty-cart">
      Ваша корзина пуста!
    </div>
    <div v-else>
      <ListView class="cart-item" :elements="cartItems" v-slot="{element: item, index}">
        <CountryFlag class="flag-icon" :country="item['flag']"/>
        <span class="product-name">{{ item['name'] }}</span>
        <div class="quantity-block">
          <button @click="item['quantity']--">–</button>
          <span class="product-quantity">{{ item['quantity'] }} шт.</span>
          <button @click="item['quantity']++">+</button>
        </div>
        <div class="cost-block">
          <span>Стоимость:</span>
          <span class="product-cost">{{ item['price'].toFixed(2) }} {{ currency_symbol }}</span>
        </div>
        <button class="remove-btn" @click="removeFromCart(item.id)">
          <TrashIcon/>
        </button>
      </ListView>
      <hr>
      <div class="total-price-block">
        <div>
          <span>Сумма к оплате:</span>
          <span class="total-price">{{totalPrice}} {{currency_symbol}}</span>
        </div>
        <CommonButton tabindex="0">Выбрать способ оплаты</CommonButton>
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

      &:hover {
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
