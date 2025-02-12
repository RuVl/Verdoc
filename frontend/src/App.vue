<script setup>
import SiteNav from "@/components/SiteNav.vue";
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
