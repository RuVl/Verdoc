<script setup>
import DropdownIcon from "@/components/icons/IconDropdown.vue";
import {ref} from "vue";

const currencies = ref([
  {code: 'usd', name: 'USD', symbol: '$'},
  {code: 'rub', name: 'RUB', symbol: '₽'},
]);

const isActive = ref(false);
const selectedCurrency = ref(currencies.value[0]);

function selectCurrency(currency) {
  selectedCurrency.value = currency;
  isActive.value = false;
}
</script>

<template>
  <div tabindex="0" class="currency-switch" :class="{ active: isActive }" @keydown.enter="isActive = !isActive" @blur="isActive = false">
    <div class="selected-currency" @click="isActive = !isActive">
      <span>{{ selectedCurrency.name }}</span>
      <DropdownIcon class="dropdown-icon"/>
    </div>

    <ul v-if="isActive" class="dropdown-menu">
      <li v-for="currency in currencies" :key="currency.code" @click="selectCurrency(currency)">
        <span>{{ currency.name }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.currency-switch {
  position: relative;
  cursor: pointer;
  color: #000000;
  font-weight: 600;
  font-size: 14px;

  span {
    user-select: none;
  }

  .selected-currency {
    display: flex;
    align-items: center;
    background-color: var(--second-color);
    border-radius: 10px;
    padding: 10px;
  }

  .dropdown-icon {
    margin-left: 10px;
    transform: scale(0.7);
    transition: transform 0.4s;
  }

  &.active .dropdown-icon {
    transform: rotate(180deg) scale(0.7);
  }

  .dropdown-menu {
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translate(-50%);
    border: 1px solid #ccc;
    background-color: #ffffff;
    border-radius: 4px;
    margin: 3px 0 0 0;
    padding: 0;

    font-weight: 500;

    width: max-content;
    list-style: none;
    z-index: 10;

    li {
      display: flex;
      align-items: center;
      padding: 5px 20px;

      &:hover {
        background-color: #f0f0f0;
      }
    }
  }
}
</style>