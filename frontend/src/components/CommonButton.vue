<script setup>
defineProps({
  href: String,
  disabled: Boolean
});
</script>

<template>
  <router-link v-if="href" class="cmn-btn" :class="{ disabled: disabled }" :to="href.startsWith('/') ? href : {name: href}">
    <slot/>
  </router-link>
  <button v-else class="cmn-btn" :class="{ disabled: disabled }">
    <slot/>
  </button>
</template>

<style lang="scss" scoped>
button.cmn-btn {
  font: inherit;
  border: none;
  line-height: inherit;
}

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
  pointer-events: none;
  opacity: .5;

  &:hover {
    cursor: default;
  }
}
</style>