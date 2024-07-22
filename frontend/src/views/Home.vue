<script setup>
import {ref, onMounted, watch} from "vue";
import CountryFlag from 'vue-country-flag-next';
import CommonButton from "@/components/CommonButton.vue";
import CurrencySwitch from "@/components/CurrencySwitch.vue";
import CartIcon from '@/components/icons/IconCart.vue'
import Block from "@/components/Block.vue";
import ProductsList from "@/components/ListView.vue";
import apiClient from "@/api/index.js";
import Country from "@/models/Country.js";
import {useCartStore} from "@/stores/cart.js";
import ModalWindow from "@/components/ModalWindow.vue";
import CounterShow from "@/components/CounterShow.vue";
import CounterChanger from "@/components/CounterChanger.vue";
import SelectPayment from "@/components/SelectPayment.vue";

const countries = ref([]);

async function fetchCountries() {
  try {
    const response = await apiClient.get('/countries/');
    countries.value = response.data.map(countryData => Country.fromApi(countryData));
  } catch (error) {
    console.error('Error fetching countries:', error);
  }
}

onMounted(fetchCountries);

const cartStore = useCartStore();

const selectedPassport = ref(null);
const instant_buy = ref(false);
const select_payment = ref(false);

watch(instant_buy, value => {
  if (!value) {
    selectedPassport.quantity = 0;
    selectedPassport.value = null;
  }
});

function add2cart(passport) {
  cartStore.addItem(passport);

  if (instant_buy.value)
    instant_buy.value = false;
}
</script>

<template>
  <Block class="site-info">
    <h2>{{ $t('site_info.title.first') }} <span style="color: var(--accent-color)">{{ $t('site_info.title.second') }}</span></h2>
    <div class="description">{{ $t('site_info.description') }}</div>
    <div class="support-btn-wrapper">
      <CommonButton style="padding: 20px 30px" href="support">{{ $t('buttons.support') }}</CommonButton>
    </div>
  </Block>

  <Block class="product-table">
    <div class="controls">
      <span>{{ $t('products.list') }}</span>
      <span class="currency-switch-wrapper">
        {{ $t('products.currency') }}:
        <CurrencySwitch/>
      </span>
    </div>
    <hr>
    <ProductsList v-for="country in countries" :key="country.id" :elements="country.passports">
      <template #title>
        <CountryFlag class="flag-icon" :country="country.code" size="big"/>
        <span>{{ country.name }}</span>
      </template>
      <template #default="{element: passport}">
        <CountryFlag class="flag-icon" :country="country.code"/>
        <span class="product-name">{{ passport.name }}</span>
        <CounterShow>{{ passport.max_quantity }} {{ $t('products.count') }}</CounterShow>
        <CounterShow>{{ passport.formattedPrice() }}</CounterShow>
        <CommonButton class="buy-now-btn" @click="selectedPassport=passport; instant_buy=true">
          {{ $t('buttons.buy_now') }}
        </CommonButton>
        <a class="add2cart-btn" @click="add2cart(passport)">
          <CartIcon/>
        </a>
      </template>
    </ProductsList>
    <ModalWindow v-model:is_opened="instant_buy">
      <template #title>
        {{ $t('products.modal_window.title') }}
      </template>
      <template #default>
        <div class="instant-buy-dialog">
          <span class="product-name">{{ selectedPassport.name }}</span>
          <CounterChanger class="quantity-counter" v-model:item="selectedPassport" counter_name="quantity"/>
          {{ $t('products.modal_window.total_amount') }}
          <span class="total-cost">{{ selectedPassport.formattedPrice(true) }}</span>
          <div class="buttons-block">
            <button class="add2cart-btn" @click="add2cart(selectedPassport)" type="button">
              <CartIcon size="small"/>
              {{ $t('buttons.add2cart') }}
            </button>
            <CommonButton type="button" @click="instant_buy=false; select_payment=true">{{ $t('buttons.buy_now') }}</CommonButton>
          </div>
        </div>
      </template>
    </ModalWindow>
    <SelectPayment v-model:is_opened="select_payment" :passport="selectedPassport"/>
  </Block>
</template>

<style scoped lang="scss">
.site-info {
  min-height: 284px;
  position: relative;
  box-sizing: border-box;
  border: none;
  padding: 50px 65px;
  background: linear-gradient(90deg, #ffffff, transparent) no-repeat right, url("@/assets/banner_background.jpg") no-repeat center right -1px;
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
    min-width: $height;
    background-position-x: calc(($height - $width) / 2);
    background-repeat: no-repeat;

    margin-bottom: 0;
  }

  .product-name {
    text-wrap: pretty;
    width: 635px;
    margin-right: 20px;
  }

  .buy-now-btn {
    margin-left: auto;
  }

  .add2cart-btn {
    display: inline-block;
    text-decoration: none;
    line-height: 0;

    &:hover {
      cursor: pointer;
      opacity: .7;
    }
  }
}

.instant-buy-dialog {
  display: flex;
  gap: 10px;
  flex-direction: column;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  min-width: 300px;

  .product-name {
    font-size: 14px;
  }

  .quantity-counter, .total-cost {
    margin-bottom: 10px;
  }

  .total-cost {
    font-size: 24px;
    font-weight: 700;
  }

  .buttons-block {
    display: flex;
    gap: 25px;
    justify-content: space-evenly;
    align-items: stretch;
    width: 100%;

    .add2cart-btn {
      text-wrap: nowrap;
      border: none;
      background: none;
      color: var(--accent-color);
      cursor: pointer;
      font-size: 14px;
      line-height: 14px;

      display: flex;
      gap: 7px;
      align-items: center;
      justify-content: center;

      &:hover {
        opacity: .7;
      }
    }
  }
}
</style>