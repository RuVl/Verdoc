<script setup>
import SiteNav from "@/components/SiteNav.vue";
</script>

<template>
  <header>
    <SiteNav extended/>
  </header>
  <main class="main-view">
    <router-view/>
  </main>
  <footer>
    <SiteNav/>
  </footer>
</template>

<style scoped>
.main-view {
  min-height: calc(100vh - ((50px + var(--navigation-margin) * 2)* 2 + var(--main-margin)));
  margin-top: var(--main-margin);
  box-sizing: content-box;
}

@media only screen and (max-width: 768px) {
  .main-view {
    margin-top: 0;
  }
}
</style>
