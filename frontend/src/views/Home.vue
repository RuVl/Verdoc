<script setup>
import {ref} from "vue";
import CountryFlag from 'vue-country-flag-next';
import CommonButton from "@/components/CommonButton.vue";
import CurrencySwitch from "@/components/CurrencySwitch.vue";
import CartIcon from '@/components/icons/IconCart.vue'
import Block from "@/components/Block.vue";
import ProductsList from "@/components/ListView.vue";

const categories = ref([
  {
    id: 1,
    flag: 'au',
    name: 'Австралия',
    products: [
      {
        id: 1,
        name: 'Австралия паспорт скан',
        quantity: 24,
        price: 123
      },
      {
        id: 2,
        name: 'Австралии DL фото с одной стороны + Drive Safely card + Medicare card',
        quantity: 24,
        price: 123
      },
      {
        id: 3,
        name: 'Австралия DL фото с двух сторон + селфи + паспорт + селфи + Австралия DL фото с двух сторон + селфи + паспорт + селфи 4 Medicare карта',
        quantity: 24,
        price: 123
      },
    ]
  },
  {
    id: 2,
    flag: 'ar',
    name: 'Аргентина',
    products: [
      {
        id: 4,
        name: 'Австралия паспорт скан',
        quantity: 24,
        price: 123
      },
      {
        id: 5,
        name: 'Австралии DL фото с одной стороны + Drive Safely card + Medicare card',
        quantity: 24,
        price: 123
      },
      {
        id: 6,
        name: 'Австралия DL фото с двух сторон + селфи + паспорт + селфи + Австралия DL фото с двух сторон + селфи + паспорт + селфи 4 Medicare карта',
        quantity: 24,
        price: 123
      },
    ]
  }
]);

const currency_symbol = ref('₽');

function buy_now(product) {
  alert('TODO: buy window');
}

function add2cart(product) {
  alert('TODO: add to cart');
}
</script>

<template>
  <Block class="site-info">
    <h2>Документы различных стран для <span style="color: var(--accent-color)">прохождения верификации</span></h2>
    <div class="description">Самый большой сайт с продажей фотографий документов, которые помогут пройти верификацию</div>

    <div class="support-btn-wrapper">
      <CommonButton style="padding: 20px 30px" href="support">Поддержка магазина</CommonButton>
    </div>
  </Block>

  <Block class="product-table">
    <div class="controls">
      <span>Список товаров</span>
      <span class="currency-switch-wrapper">
        Валюта:
        <CurrencySwitch/>
      </span>
    </div>
    <hr>
    <ProductsList v-for="category in categories" class="" :elements="category.products">
      <template #title>
        <CountryFlag class="flag-icon" :country="category.flag" size="big"/>
        <span>{{ category.name }}</span>
      </template>
      <template #default="{element: product}">
        <CountryFlag class="flag-icon" :country="category.flag"/>
        <span class="product-name">{{ product['name'] }}</span>
        <span class="product-quantity">{{ product['quantity'] }} шт.</span>
        <span class="product-cost">{{ product['price'].toFixed(2) }} {{ currency_symbol }}</span>
        <CommonButton class="buy-now-btn" :action="() => buy_now(product)">Купить сейчас</CommonButton>
        <a class="add2cart-btn" @click="add2cart(product)">
          <CartIcon/>
        </a>
      </template>
    </ProductsList>
  </Block>
</template>

<style scoped lang="scss">
.site-info {
  min-height: 284px;
  position: relative;
  box-sizing: border-box;
  padding: 50px 65px;
  background: linear-gradient(90deg, #ffffff, transparent) no-repeat right, url("@/assets/banner_background.jpg") no-repeat right;
  background-size: min(100%, var(--banner-width)) 100%, auto 100%;

  & > h2 {
    max-width: 525px;
    line-height: 45px;
    font-size: 30px;
    font-weight: 600;
    margin-bottom: 25px;
  }

  & > .description {
    max-width: 445px;
    font-size: 14px;
    font-weight: 500;
    line-height: 24px;
  }

  & > .support-btn-wrapper {
    position: absolute;
    top: 100%;
    bottom: 0;
    line-height: 0;
  }
}

.product-table {
  margin-top: 100px;

  .controls {
    display: flex;
    align-items: center;
    font-size: 14px;
    font-weight: 600;

    span {
      text-wrap: nowrap;
    }

    .currency-switch-wrapper {
      font-weight: 500;
      font-size: 12px;

      display: flex;
      align-items: center;
      gap: 15px;
      color: var(--second-color-text);
    }

    & > *:last-child {
      margin-left: auto;
    }
  }

  hr {
    margin: 25px 0;
    border: 0;
    border-top: 1px solid var(--second-color);
  }

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

  .buy-now-btn {
    margin-left: auto;
  }

  .add2cart-btn {
    text-decoration: none;
    line-height: 0;

    &:hover {
      cursor: pointer;
      opacity: .7;
    }
  }
}
</style>