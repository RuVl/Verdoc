<script setup>
import Logo from "@/components/Logo.vue";
import LanguageSwitch from "@/components/LanguageSwitch.vue";
import CartButton from "@/components/CartButton.vue";

defineProps({
  links: {
    type: Array,
    default: [
      {name: 'Как работает?', path_name: 'info'},
      {name: 'Контакты', path_name: 'contacts'},
      {name: 'Мои покупки', path_name: 'purchases'}
    ],
    validator(value) {
      return value.every((v) => v.hasOwnProperty('name') && v.hasOwnProperty('path_name'));
    }
  },
  extended: Boolean
});
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
