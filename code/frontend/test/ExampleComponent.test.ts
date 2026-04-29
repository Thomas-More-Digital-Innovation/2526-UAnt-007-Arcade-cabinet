import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import ExampleComponent from '../src/components/ExampleComponent.vue';

describe('ExampleComponent', () => {
  it('renders the title', () => {
    const wrapper = mount(ExampleComponent, {
      props: {
        title: 'Hello World',
        meta: { totalCount: 10 },
        active: true,
        todos: []
      }
    });
    expect(wrapper.text()).toContain('Hello World');
  });

  it('renders todos', () => {
    const todos = [
      { id: 1, content: 'Todo 1' },
      { id: 2, content: 'Todo 2' }
    ];
    const wrapper = mount(ExampleComponent, {
      props: {
        title: 'Todos',
        meta: { totalCount: 2 },
        active: true,
        todos
      }
    });
    expect(wrapper.findAll('li')).toHaveLength(2);
    expect(wrapper.text()).toContain('Todo 1');
    expect(wrapper.text()).toContain('Todo 2');
  });

  it('increments click count when a todo is clicked', async () => {
    const todos = [{ id: 1, content: 'Todo 1' }];
    const wrapper = mount(ExampleComponent, {
      props: {
        title: 'Click test',
        meta: { totalCount: 1 },
        active: true,
        todos
      }
    });
    
    expect(wrapper.text()).toContain('Clicks on todos: 0');
    await wrapper.find('li').trigger('click');
    expect(wrapper.text()).toContain('Clicks on todos: 1');
  });
});
