<template>
  <span class="counter"><slot/></span>
</template>

<style scoped lang="scss">
.counter {
  display: inline-block;
  text-align: center;
  min-width: 100px;
  padding: 10px 0;
  background-color: var(--second-color);
  border-radius: 10px;
}
</style>