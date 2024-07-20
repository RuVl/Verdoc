<script setup>
import {ref, computed} from 'vue';
import {useI18n} from 'vue-i18n';
import Logo from "@/components/Logo.vue";
import LanguageSwitch from "@/components/LanguageSwitch.vue";
import CartButton from "@/components/CartButton.vue";

defineProps({
  extended: Boolean
});

const {t} = useI18n();
const ct = (msg) => computed(() => t(msg));

const links = ref([
  {name: ct('navigation.how_it_works'), path_name: 'info'},
  {name: ct('navigation.contacts'), path_name: 'contacts'},
  {name: ct('navigation.my_purchases'), path_name: 'purchases'}
]);
</script>

<template>
  <div class="navigation-wrapper">
    <Logo/>
    <LanguageSwitch v-if="extended"/>
    <nav class="navbar">
      <router-link v-for="link in links" :to="{name: link.path_name}" class="nav-link">
        {{ link.name }}
      </router-link>
    </nav>
    <CartButton v-if="extended"/>
  </div>
</template>

<style lang="scss" scoped>
.navigation-wrapper {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 45px;

  box-sizing: content-box;
  padding: var(--navigation-margin) 0;
  height: 50px;

  > *:last-child {
    margin-left: auto;
  }

  > .navbar {
    display: flex;
    align-items: center;
    height: 100%;
    gap: 35px;

    > .nav-link {
      text-wrap: nowrap;
      text-decoration: none;
      color: #000;
      font-size: 16px;
      font-weight: 500;
      transition: color 0.3s;

      &:hover {
        color: #2f61f2;
      }
    }
  }
}
</style>
