<script setup>
defineProps({
  size: {
    type: String,
    default: 'normal',
    validator(value) {
      return ['small', 'normal', 'large'].includes(value);
    }
  }
});
</script>

<template>
  <svg :class="size" class="i-copy" fill="currentColor" viewBox="0 0 448 512" xmlns="http://www.w3.org/2000/svg">
    <path d="M208 0L332.1 0c12.7 0 24.9 5.1 33.9 14.1l67.9 67.9c9 9 14.1 21.2 14.1 33.9L448 336c0 26.5-21.5 48-48 48l-192 0c-26.5 0-48-21.5-48-48l0-288c0-26.5 21.5-48 48-48zM48 128l80 0 0 64-64 0 0 256 192 0 0-32 64 0 0 48c0 26.5-21.5 48-48 48L48 512c-26.5 0-48-21.5-48-48L0 176c0-26.5 21.5-48 48-48z"/>
  </svg>
</template>

<style scoped>
.i-copy {
  display: block;
}

.i-copy.small {
  width: 14px;
}

.i-copy.normal {
  width: 18px;
}

.i-copy.large {
  width: 25px;
}
</style>
