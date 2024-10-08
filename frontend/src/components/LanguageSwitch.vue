<script setup>
import {ref} from 'vue';
import {useLanguagesStore} from '@/stores/languages';
import CountryFlag from 'vue-country-flag-next';
import DropdownIcon from '@/components/icons/IconDropdown.vue';

const isActive = ref(false);
const languagesStore = useLanguagesStore();

function setLanguage(language) {
  languagesStore.setLanguage(language).then(
      () => {isActive.value = false}
  );
}
</script>

<template>
  <div tabindex="0" class="lang-switch" :class="{ active: isActive }" @blur="isActive = false" @keydown.enter="isActive = !isActive">
    <div class="selected-flag" @click="isActive = !isActive">
      <CountryFlag :country="languagesStore.currentLanguage.flag" class="flag-icon"/>
      <DropdownIcon class="dropdown-icon"/>
    </div>

    <ul v-if="isActive" class="dropdown-menu">
      <li v-for="language in languagesStore.languages" :key="language.code" @click="setLanguage(language)">
        <CountryFlag :country="language.flag" class="flag-icon"/>
        <span class="lang-name">{{ language.name }}</span>
      </li>
    </ul>
  </div>
</template>

<style lang="scss" scoped>
.lang-switch {
  position: relative;
  cursor: pointer;

  .selected-flag {
    display: flex;
    align-items: center;
  }

  .flag-icon {
    margin-bottom: 0;
    transform: scale(.5, .45);
  }

  .dropdown-icon {
    margin-left: 3px;
    transform: scale(0.7);
    transition: transform 0.4s;
  }

  &.active .dropdown-icon {
    transform: rotate(180deg) scale(0.7);
  }

  .dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    border: 1px solid #ccc;
    background-color: #ffffff;
    border-radius: 4px;
    margin: 5px 0 0 0;
    padding: 0;

    width: max-content;
    list-style: none;
    z-index: 10;

    li {
      display: flex;
      align-items: center;
      padding: 0 3px;

      &:hover {
        background-color: #f0f0f0;
      }

      .lang-name {
        user-select: none;
        margin-left: 10px;
      }
    }
  }
}
</style>
