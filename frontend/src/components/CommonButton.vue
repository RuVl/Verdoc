<script setup>
defineProps({
  href: String,
  action: {
    type: Function,
    default: () => console.warn('Not implemented!')
  },
  disabled: Boolean
});
</script>

<template>
  <router-link v-if="href" class="cmn-btn" :class="{ disabled: disabled }" :to="disabled ? '' : href.startsWith('/') ? href : {name: href}">
    <slot></slot>
  </router-link>
  <a v-else @click="disabled ? '' : action()" class="cmn-btn" :class="{ disabled: disabled }">
    <slot></slot>
  </a>
</template>

<style lang="scss" scoped>
.cmn-btn {
  place-content: center;
  text-decoration: none;
  color: #ffffff;
  background-color: var(--accent-color);
  box-shadow: 0 5px 65px 0 color-mix(in srgb, var(--accent-color) 60%, transparent);
  border-radius: 30px;
  padding: 10px 20px;
  user-select: none;

  &:hover {
    cursor: pointer;
    opacity: .9;
  }
}

.cmn-btn.disabled {
  opacity: .5;

  &:hover {
    cursor: default;
  }
}
</style>