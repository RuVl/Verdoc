<script setup>
import {ref, computed} from 'vue';
import {useI18n} from 'vue-i18n';
import Logo from "@/components/Logo.vue";
import LanguageSwitch from "@/components/LanguageSwitch.vue";
import CartButton from "@/components/CartButton.vue";
import HamburgerIcon from "@/components/icons/IconHamburger.vue";

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

const is_active = ref(false);
</script>

<template>
  <div class="navigation-wrapper" :class="{extended: extended}">
    <div class="logo-wrapper">
      <Logo/>
    </div>
    <LanguageSwitch v-if="extended" class="lang-switch"/>
    <HamburgerIcon v-if="extended" v-model:is_active="is_active" class="burger-btn" tabindex="0"/>
    <nav class="navbar" :class="{active: is_active}">
      <router-link v-for="link in links" :to="{name: link.path_name}" class="nav-link" @click="is_active=false">
        {{ link.name }}
      </router-link>
    </nav>
    <CartButton v-if="extended" class="cart-btn"/>
  </div>
</template>

<style lang="scss" scoped>
.navigation-wrapper {
  position: relative;
  display: flex;
  flex-flow: wrap row;
  align-items: center;
  gap: 30px 45px;

  box-sizing: content-box;
  padding: var(--navigation-margin) 0;

  .logo-wrapper {
    display: flex;
    align-items: center;
  }

  .burger-btn {
    display: none;
  }

  > .cart-btn {
    margin-left: auto;
  }
}

nav.navbar {
  display: flex;
  align-items: center;
  height: 100%;
  gap: 15px 35px;

  .nav-link {
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

@media only screen and (max-width: 1024px) {
  // Extended with lang-switch, burger-btn, and cart-btn
  .navigation-wrapper.extended {
    $navbar-height: 100px;
    $burger-size: 50px;
    $vertical-gap: 30px;
    gap: $vertical-gap 0;

    .logo-wrapper {
      flex: calc(100% - $burger-size * 2);
      height: $burger-size;
      align-self: flex-start;
    }

    .lang-switch, .cart-btn {
      order: 1;
    }

    .burger-btn {
      flex: $burger-size 0;
      border: 1px solid black;
      border-radius: 10px;
      padding: 5px 0;

      display: block;
      stroke: black;
      transform: scale(.7);

      &.active {
        margin-bottom: $navbar-height;
      }
    }

    nav.navbar:not(.active) {
      display: none;
    }

    nav.navbar.active {
      position: absolute;
      display: flex;
      flex-flow: nowrap column;
      height: $navbar-height;
      margin-bottom: calc($vertical-gap / -2);
      width: 100%;
      gap: 0;

      > .nav-link {
        margin-top: auto;
      }
    }
  }

  .navigation-wrapper:not(.extended) {
    justify-content: center;

    nav.navbar {
      margin-left: 0;
      flex-wrap: wrap;
      justify-content: center;
    }
  }
}

@media only screen and (max-width: 350px) {
  .navigation-wrapper:not(.extended) {
    nav.navbar > .nav-link {
      font-size: 14px;
    }
  }
}
</style>
