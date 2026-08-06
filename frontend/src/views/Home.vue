<script setup>
import {onMounted, ref} from "vue";
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
const loading = ref(true);
const failed = ref(false);

async function fetchCountries() {
  loading.value = true;
  failed.value = false;
  try {
    const response = await apiClient.get('/countries/');
    countries.value = response.data
        .map(countryData => Country.fromApi(countryData))
        .sort((a, b) => a.name.localeCompare(b.name));
  } catch (error) {
    // An empty table looks the same as a sold-out catalogue, so say which one it is.
    failed.value = true;
    console.error('Error fetching countries:', error);
  } finally {
    loading.value = false;
  }
}

onMounted(fetchCountries);

const cartStore = useCartStore();

const selectedProduct = ref(null);
const instant_buy = ref(false);
const select_payment = ref(false);

function add2cart(product) {
  cartStore.addItem(product);

  if (instant_buy.value)
    instant_buy.value = false;
}
</script>

<template>
  <Block class="site-info">
    <h2>{{ $t('site_info.title.first') }} <span style="color: var(--accent-color)">{{
        $t('site_info.title.second')
      }}</span></h2>
    <div class="description">{{ $t('site_info.description') }}</div>
    <div class="support-btn-wrapper">
      <CommonButton href="support">{{ $t('buttons.support') }}</CommonButton>
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

    <p v-if="loading" class="notice">{{ $t('products.loading') }}</p>

    <div v-else-if="failed" class="notice failed">
      <p>{{ $t('products.error') }}</p>
      <CommonButton type="button" @click="fetchCountries">{{ $t('buttons.retry') }}</CommonButton>
    </div>

    <p v-else-if="!countries.length" class="notice">{{ $t('products.empty') }}</p>

    <ProductsList v-for="country in countries" :key="country.id" :elements="country.products">
      <template #title>
        <CountryFlag :country="country.code" class="flag-icon" size="big"/>
        <span>{{ country.name }}</span>
      </template>
      <template #default="{element: product}">
        <CountryFlag :country="country.code" class="flag-icon item"/>
        <span class="product-name">{{ product.name }}</span>
        <span class="counters">
          <CounterShow>{{ product.max_quantity }} {{ $t('products.count') }}</CounterShow>
          <CounterShow>{{ product.formattedPrice() }}</CounterShow>
        </span>
        <CommonButton class="buy-now-btn" @click="selectedProduct=product; instant_buy=true">
          <span class="longer">{{ $t('buttons.buy_now') }}</span>
          <span class="shorter">{{ $t('buttons.buy') }}</span>
        </CommonButton>
        <a class="add2cart-btn" @click="add2cart(product)">
          <CartIcon/>
          <span>{{ $t('buttons.to_cart') }}</span>
        </a>
      </template>
    </ProductsList>
    <ModalWindow v-model:is_opened="instant_buy">
      <template #title>
        {{ $t('products.modal_window.title') }}
      </template>
      <template #default>
        <div class="instant-buy-dialog">
          <span class="product-name">{{ selectedProduct.name }}</span>
          <CounterChanger v-model:item="selectedProduct" class="quantity-counter" counter_name="quantity"/>
          {{ $t('products.modal_window.total_amount') }}
          <span class="total-cost">{{ selectedProduct.formattedPrice(true) }}</span>
          <div class="buttons-block">
            <button class="add2cart-btn" type="button" @click="add2cart(selectedProduct)">
              <CartIcon size="small"/>
              {{ $t('buttons.add2cart') }}
            </button>
            <CommonButton type="button" @click="instant_buy=false; select_payment=true">{{
                $t('buttons.buy_now')
              }}
            </CommonButton>
          </div>
        </div>
      </template>
    </ModalWindow>
    <SelectPayment v-model:is_opened="select_payment" :product="selectedProduct"/>
  </Block>
</template>

<style lang="scss" scoped>
.site-info {
  min-height: 284px;
  position: relative;
  box-sizing: border-box;
  border: none;
  padding: 50px 65px;
  background: linear-gradient(90deg, #ffffff, transparent) no-repeat right, url("@/assets/banner_background.jpg") no-repeat center right -10px;
  background-size: min(100%, var(--banner-image-width)) 100%, auto 100%;

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

    > * {
      padding: 20px 30px;
    }
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

  .notice {
    font-size: 16px;
    line-height: 24px;
  }

  .notice.failed {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 20px;
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

  // single-row grid: name column shrinks, no fixed widths
  :deep(.products-list > ul > li) {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto auto;
    align-items: center;
    gap: 10px 25px;
  }

  .product-name {
    // robustly override the `text-wrap: nowrap` inherited from ListView's li;
    // white-space is universally supported, unlike `text-wrap: pretty` alone
    white-space: normal;
    overflow-wrap: anywhere;
    text-wrap: pretty; // progressive enhancement for nicer line breaks
  }

  .counters {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    min-width: 0;
    gap: 25px;
  }

  .buy-now-btn {
    .shorter {
      display: none;
    }
  }

  .add2cart-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    line-height: 0;

    &:hover {
      cursor: pointer;
      opacity: .7;
    }

    span {
      display: none;
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

// phone layout per design mockup: name + buy on top, counters + cart below
@media screen and (max-width: 768px) {
  .product-table {
    :deep(.products-list > ul > li) {
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas:
        "name buy"
        "counters cart";
    }

    .item.flag-icon {
      display: none;
    }

    .product-name {
      grid-area: name;
    }

    .counters {
      grid-area: counters;
      gap: 10px;
    }

    .buy-now-btn {
      grid-area: buy;
    }

    .add2cart-btn {
      grid-area: cart;
      justify-self: end;

      span {
        display: inline;
      }
    }
  }
}

@media screen and (max-width: 480px) {
  .site-info {
    text-align: center;
    min-height: 0;
    background: linear-gradient(90deg, #ffffff, #ffffff7f) no-repeat right, url("@/assets/banner_background.jpg") no-repeat center left -1px;
    background-size: 100%, auto 100%;
    padding: 35px 20px 50px 20px;

    h2 {
      text-align: center;
      font-size: 20px;
      line-height: 30px;
      font-weight: 700;
      text-wrap: balance;
    }

    .description {
      display: inline-block;
      text-align: center;
      font-size: 12px;
      width: 90%;
    }

    .support-btn-wrapper {
      left: 0;
      right: 0;
      text-align: center;

      > * {
        padding: 15px 20px;
      }
    }
  }

  .product-table {
    :deep(.products-list > ul > li) {
      gap: 10px 15px;
    }

    .notice {
      font-size: 14px;
      text-align: center;
    }

    .notice.failed {
      align-items: center;
    }

    .controls .currency-switch-wrapper {
      font-size: 0;
    }

    .counters {
      gap: 5px;

      .counter {
        min-width: 80px;
      }
    }

    .buy-now-btn {
      .shorter {
        display: inline;
      }

      .longer {
        display: none;
      }
    }
  }
}
</style>