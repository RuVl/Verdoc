<script setup>
const model = defineModel()
</script>

<template>
  <input class="pretty-input" v-model="model"/>
</template>

<style lang="scss">
input.pretty-input {
  min-width: 260px;
  height: 45px;
  padding: 0 30px;

  border: 0;
  border-radius: 25px;
  box-shadow: 0 0 8px 0 rgba(0, 0, 0, 0.14) inset;

  &::placeholder {
    color: var(--second-color-text);
  }

  &:focus, &:focus-visible {
    outline: 1px solid var(--second-color);
  }
}

@media only screen and (max-width: 480px) {
  input.pretty-input {
    padding: 0 15px;
    height: 35px;
    min-width: auto;
    width: 75%;
  }
}
</style>