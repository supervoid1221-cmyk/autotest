<template>
  <n-dynamic-input
    v-model:value="inputData"
    :on-create="onCreate"
    :on-remove="onRemove"
    #="{ value }"
  >
    <tr>
      <td>
        <n-input
          v-model:value="value.name"
          type="text"
          placeholder="断言名称"
          @update:value="onChange"
        />
      </td>
      <td>
        <n-input
          v-model:value="value.a"
          type="text"
          placeholder="预期结果"
          @update:value="onChange"
        />
      </td>
      <td>
        <n-select
          v-model:value="value.operation"
          :options="AssertOptions"
          placeholder="比较方式"
          width="100%"
          :consistent-menu-width="false"
          @update:value="onChange"
        />
      </td>
      <td
        ><n-input v-model:value="value.b" min="0" placeholder="实际结果" @update:value="onChange"
      /></td>
    </tr>
  </n-dynamic-input>
</template>

<script lang="ts" setup>
  import { ref, computed, Ref, watchEffect } from 'vue';
  import { AssertOptions } from './apiSelectOptions';

  interface InputDataItem {
    name: string;
    operation: string;
    a: string;
    b: string;
  }

  const props = defineProps({
    data: {
      type: Object,
      required: true,
    },
  });
  const emit = defineEmits(['someEvent']);

  // 子组件输入的值
  const inputData: Ref<InputDataItem[]> = ref([onCreate()]);

  //子组件传出的值
  const dictDict = computed(() =>
    inputData.value.reduce((acc, curr) => {
      acc[curr.operation] = acc[curr.operation] || {};
      acc[curr.operation][curr.name] = [curr.a, curr.b];
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
  // const formModel = ref({
  //   inputData,
  // });
  //
  // const DuplicateNameRule = {
  //   trigger: 'input',
  //   validator(rule: unknown, value: string) {
  //     if (inputKeys.value.filter((element) => element === value).length > 1)
  //       return new Error('Name重复');
  //     return true;
  //   },
  // };

  function onCreate() {
    return {
      name: '',
      operation: 'equals',
      a: '',
      b: '',
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

    if (inputKeys.value.length === 1 && inputKeys.value[0] === '' && props.data) {
      inputData.value = [];

      const entries: [string, object][] = Object.entries(props.data);
      entries.map(([operation, expr]) => {
        let name = '';
        let a = '';
        let b = '';

        Object.entries(expr).map(([key, value]: [string, string[]]) => {
          name = key.toString();
          a = value[0].toString();
          b = value[1].toString();
          inputData.value.push({
            operation,
            name,
            a,
            b,
          });
        });
      });
      // console.log(inputData.value);
    }
  });
</script>
