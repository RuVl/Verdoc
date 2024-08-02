<script setup>

</script>

<template>
<div class="block">
  <slot/>
</div>
</template>

<style scoped lang="scss">
.block {
  background: #ffffff;
  border-radius: 40px;
  box-shadow: 0 5px 109px 0 rgba(20, 29, 50, 0.29);
  padding: 25px 40px 60px 40px;
}

@media only screen and (max-width: 480px) {
  .block {
    padding: 25px 20px 40px 20px;
  }
}
</style>