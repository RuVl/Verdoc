<script setup>
import {onBeforeUnmount, onMounted} from "vue";
import SiteNav from "@/components/SiteNav.vue";
import {EXCHANGE_RATES_INTERVAL_MS, useCurrenciesStore} from "@/stores/currencies.js";

// The rates belong to the running app, not to the module: fetched once it is mounted (pinia is
// installed by then) and refreshed on a timer this component also clears.
const currenciesStore = useCurrenciesStore();
let ratesTimer = null;

onMounted(() => {
  currenciesStore.updateExchangeRates();
  ratesTimer = setInterval(() => currenciesStore.updateExchangeRates(), EXCHANGE_RATES_INTERVAL_MS);
});

onBeforeUnmount(() => {
  if (ratesTimer !== null) clearInterval(ratesTimer);
});
</script>

<template>
  <header>
    <SiteNav extended/>
  </header>
  <main>
    <router-view/>
  </main>
  <footer>
    <SiteNav/>
  </footer>
</template>

<style scoped>
main {
  box-sizing: content-box;
}

footer {
  margin-top: auto;
}
</style>
