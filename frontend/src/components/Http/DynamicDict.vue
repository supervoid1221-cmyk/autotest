<template>
  <n-form :model="formModel">
    <n-dynamic-input
      v-model:value="inputData"
      item-style="margin-bottom: 0;"
      :on-create="onCreate"
      :on-remove="onRemove"
      #="{ index, value }"
    >
      <div style="display: flex">
        <!--
                  通常，path 的变化会导致 form-item 验证内容或规则的改变，所以 naive-ui 会清理掉
                  表项已有的验证信息。但是这个例子是个特殊情况，我们明确的知道，path 的改变不会导致
                  form-item 验证内容和规则的变化，所以就 ignore-path-change
                -->
        <n-form-item
          ignore-path-change
          :show-label="false"
          :rule="DuplicateNameRule"
          :path="`inputData[${index}].name`"
        >
          <n-input
            v-model:value="inputData[index].name"
            placeholder="Name"
            @keydown.enter.prevent
            @update:value="onChange"
          />
          <!--
                      由于在 input 元素里按回车会导致 form 里面的 button 被点击，所以阻止了默认行为
                    -->
        </n-form-item>
        <div style="height: 34px; line-height: 34px; margin: 0 8px"> =</div>
        <n-form-item ignore-path-change :show-label="false">
          <n-input
            v-model:value="inputData[index].value"
            placeholder="Value"
            @keydown.enter.prevent
            @update:value="onChange"
          />
        </n-form-item>
      </div>
    </n-dynamic-input>
  </n-form>
</template>

<script lang="ts" setup>
  import { computed, Ref, ref, watchEffect } from 'vue';

  interface InputDataItem {
    name: string;
    value: string;
  }

  const props = defineProps({
    data: {
      type: Object,
      required: true,
    },
  });
  const emit = defineEmits(['someEvent']);
  // 子组件输入的值
  const inputData: Ref<InputDataItem[]> = ref([{ value: '', name: '' }]);

  //子组件传出的值
  const dictDict = computed(() =>
    inputData.value.reduce((acc, curr) => {
      if (curr.name || curr.value) {
        acc[curr.name] = curr.value;
      }
      return acc;
    }, {})
  );

  // 判断key重复
  const inputKeys = computed(() =>
    inputData.value.reduce((acc: string[], curr) => {
      acc.push(curr.name);
      return acc;
    }, [])
  );

  // 表单的model属性
  const formModel = ref({
    inputData,
  });

  const DuplicateNameRule = {
    trigger: 'input',
    validator(rule: unknown, value: string) {
      if (inputKeys.value.filter((element) => element === value).length > 1)
        return new Error('Name重复');
      return true;
    },
  };

  function onCreate() {
    return {
      name: '',
      value: '',
    };
  }

  function onChange() {
    emit('someEvent', dictDict.value);
    return 1;
  }

  function onRemove() {
    setTimeout(() => onChange(), 20);
  }

  watchEffect(() => {
    // console.log(`props.data`, props.data);

    if (inputKeys.value.length <= 1 && props.data) {
      const _arr = Object.entries(props.data).map(([name, value]) => ({
        name: name.toString(),
        value: value.toString(),
      }));
      _arr.push({ value: '', name: '' });
      inputData.value = _arr;
    }
  });
</script>
