<script setup>
defineProps({
  count: {
    type: Number,
    required: true
  }
})
</script>

<template>
  <div class="circle-counter">
    <span>{{ count }}</span>
  </div>
</template>

<style scoped lang="scss">
.circle-counter {
  width: 21px;
  height: 21px;
  background-color: var(--accent-color);
  border-radius: 100%;
  text-align: center;
  vertical-align: middle;

  span {
    font-size: 13px;
    color: #fff;
  }
}
</style>