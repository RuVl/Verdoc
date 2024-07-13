<script setup>

</script>

<template>
<div class="input-wrapper">
  <slot/>
</div>
</template>

<style lang="scss">
.input-wrapper {
  width: fit-content;

  & > input {
    width: 260px;
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
}
</style>