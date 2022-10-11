# Multidimensional ndarrays memory layout (order)

## Order  

`order` is the parameter given the `numpy.array` in order to choose how the array is stored in memory, both  `Pyccel` supported orders are stored contiguously in memory, they differ in the order - the order of the values -.
`order='F'` would tell `numpy` to store the array column by column (column-major), example:
```python
import numpy as np

if __name__ == "__main__":
  a = np.array([[1, 2, 3],
                [4, 5, 6],
                [7, 8, 9]], order='F')
  print(a.ravel('K'))
```
`array.ravel('k')` shows us how the array is actually stored in memroy, this python program will output `[1 4 7 2 5 8 3 6 9]`, notice that the columns are stored one after the other.  

`order='C'` on the other hand would tell `numpy` to store the array row by row, example:
```python
import numpy as np

if __name__ == "__main__":
  a = np.array([[1, 2, 3],
                [4, 5, 6],
                [7, 8, 9]], order='C') # order='C' is the default in numpy.array
  print(a.ravel('K'))
 ```
This python program will output `[1 2 3 4 5 6 7 8 9]`, notice that the rows are stored one after the other.

### Printing and indexing in `numpy`

`order` in `numpy` doesn't not affect the indexing or the printing, unlike `transposing`, the `shape` of the array remains the same, only the `strides` change, example:
```python
import numpy as np

if __name__ == "__main__":
   a = np.array([[1, 2],
                [4, 5],
                [7, 8]], order='F')
   b = np.array([[1, 2],
                [4, 5],
                [7, 8]], order='C')
   print(a.shape, a.strides) # output: (3, 2) (8, 24)
   print(b.shape, b.strides) # output: (3, 2) (16, 8)
   print(a)
   # output:[[1 2]
   #         [4 5]
   #         [7 8]] 
   print(b)
   # output:[[1 2]
   #         [4 5]
   #         [7 8]]
   
   print(a[2][1], a[0][0], a[1]) # output: 8 1 [4 5]
   print(b[2][1], b[0][0], b[1]) # output: 8 1 [4 5]
```
`arr.strides` is how the printing and indexing occures, the strides of an array tell us how many bytes we have to skip in memory to move to the next position along a certain axis (dimension). For example for `memory_layout_of_a = [1 4 7 2 5 8]` and `strides_of_a = (8, 24)`, we have to skip 8 bytes (1 value for `int64`) to move to the next row, but 24 bytes (3 values for `int64`) to get to the same position in the next column of `a`.  
`a[2][1]` would give us `'8'`, using the `strides`: `2 * 8 + 1 * 24 = 40`, which means that in the flattened array, we would have to skip `40` bytes to get the value of `a[2][1]`, each element is 8 bytes, so we would have to skip `40 / 8 = 5` elements, from `1` to `5` to get to `'8'`


### Ordering in C
For `C`, arrays are flattened into a one dimensional string, `strides` and `shape` are used to navigate the array.
While the `order_c` `ndarrays` only require a simple copy to be created/populated, `order_f` arrays require an extra step, which is transposing the array.  
Example:  
  `order_c`  
    1.  allocate `order_c` `ndarray`  
    2.  copy values to `ndarray`  
  `order_f`  
    1. allocate temporary `order_c` `ndarray`  
    2. copy values to temporary `ndarray`  
    3. allocate `order_f` `ndarray`  
    4. copy temporary `ndarray` to final `ndarray` using `strides` and `shape`, this will create a transposed version of the temporary `ndarray`

### Indexing in C

For indexing, the function `GET_ELEMENT(arr, type, ...)` is used, indexing does not change with `order`.  
If we take the following 2D array as an example:
|   |   |   |
|---|---|---|
| 1 | 2 | 3 |
| 4 | 5 | 6 |

with `array.rows = 2` and `array.columns = 3`  
`GET_ELEMENT(arr, int32, 0, 1)` which is equivelant to `arr[0][1]` would return `2` no matter the `order`.  

To loop efficiently in an (`order_c`) array, we would do this:  
```c
for (int i = 0; i < array.rows; ++i)
{
  for (int j = 0; j < array.columns; ++j)
  {
    GET_ELEMENT(array, int32, i, j) = ...;
  }
}
```

For (`order_f`) we would do this:

```c
for (int i = 0; i < array.columns; ++i)
{
  for (int j = 0; j < array.rows; ++j)
  {
    GET_ELEMENT(array, int32, j, i) = ...;
  }
}
```

## `order_c` array creation example

To create an (`order_c`) `ndarray`, we simply copy the flattened data to our `ndarray`'s `raw_data`.  

If the data is composed of literals only (ex: np.array([1, 2, 3])), a `array_dummy` is created, before copying it to our destination `ndarray`.  
Example:  

```python
if __name__ == "__main__":
  import numpy as np
  a = np.array([[1, 2, 3], [4, 5, 6]])
```  

Would translate to:  

```c
int main()
{
    t_ndarray a = {.shape = NULL};
    a = array_create(2, (int64_t[]){2, 3}, nd_int64, false, order_c);
    int64_t array_dummy[] = {1, 2, 3, 4, 5, 6}; // Creation of an array_dummy containing the literals, notice the data has been flattened
    memcpy(a.nd_int64 + (a.current_length) , array_dummy, 6 * a.type_size); // Copying from array_dummy to our ndarray 'a'
    a.current_length += 6; // Current length helps us when multiple copy operations are needed, it is useless in this example (is there a better way?)
    free_array(a);
    return 0;
}
```  
  
If the data is composed of at least one variable array, we would use a series of copy operations to our `ndarray`.  

Example:  

```python
if __name__ == "__main__":
  import numpy as np
  a = np.array([1, 2, 3])
  b = np.array([4, 5, 6])
  c = np.array([a, [7, 8, 9], b])
```  

Would translate to this (focus on `c` creation):  

```c
int main()
{
    t_ndarray a = {.shape = NULL};
    t_ndarray b = {.shape = NULL};
    t_ndarray c = {.shape = NULL};
    a = array_create(1, (int64_t[]){3}, nd_int64, false, order_c);
    int64_t array_dummy[] = {1, 2, 3};
    memcpy(a.nd_int64 + (a.current_length) , array_dummy, 3 * a.type_size);
    a.current_length += 3;
    b = array_create(1, (int64_t[]){3}, nd_int64, false, order_c);
    int64_t array_dummy_0001[] = {4, 5, 6};
    memcpy(b.nd_int64 + (b.current_length) , array_dummy_0001, 3 * b.type_size);
    b.current_length += 3;
    
    // 'c' ndarray creation starts here, 'c' is [a, [7, 8, 9], b]
    
    c = array_create(2, (int64_t[]){3, 3}, nd_int64, false, order_c); // Allocating 'c' ndarray
    array_copy_data(&c, a); // Copying the first element of 'c'
    int64_t array_dummy_0002[] = {7, 8, 9}; // Creating an array_dummy with 'c''s second element's literals ([7, 8, 9])
    memcpy(c.nd_int64 + (c.current_length) , array_dummy_0002, 3 * c.type_size); // Copying the second element to 'c' ndarray, using 'current_length' as an offset
    c.current_length += 3; // Incrementing 'current_length' to use as an offset
    array_copy_data(&c, b); // Copying the third element to 'c' ndarray
    free_array(a);
    free_array(b);
    free_array(c);
    return 0;
}
```  

## `order_f` array creation example

For (`order_f`), the process is similar to (`order_c`), but instead of copying our data straight to the destination `ndarray`, we first create an (`order_c`) `temp_ndarray`, then after finishing the copy operations, we copy a transposed version of `temp_ndarray` to our destination `ndarray`.  

Example:

```python
if __name__ == "__main__":
  import numpy as np
  a = np.array([[1, 2, 3], [4, 5, 6]], order="F")
  print(a[0][0]) output ==> 1
```  

Would be translated to this:  

```c
int main()
{
    t_ndarray a = {.shape = NULL};
    a = array_create(2, (int64_t[]){2, 3}, nd_int64, false, order_f); // Allocation the required ndarray
    t_ndarray temp_array = {.shape = NULL};
    temp_array = array_create(2, (int64_t[]){2, 3}, nd_int64, false, order_c); // Allocating an order_c temp_array
    int64_t array_dummy[] = {1, 2, 3, 4, 5, 6}; // array_dummy with our flattened data
    memcpy(temp_array.nd_int64 + (temp_array.current_length) , array_dummy, 6 * temp_array.type_size); // Copying our array_dummy to our temp ndarray
    temp_array.current_length += 6; // Usless in this situation
    array_copy_data(&a, temp_array); // Copying/Transposing temp_array to the required ndarray
    free_array(temp_array); // Freeing the temp_array right after we were done with it
    printf("%ld\n", GET_ELEMENT(a, nd_int64, (int64_t)0, (int64_t)0)); // output ==> 1
    free_array(a);
    return 0;
}
```

If the data is composed of at least one variable array, the process would still be somewhat the same as an (`order_c`) ndarray creation, with the only changes being: the creation of a `temp_array` and the transpose/copy like operation at the end.  

Example:  

```python
if __name__ == "__main__":
  import numpy as np
  a = np.array([1, 2, 3])
  b = np.array([4, 5, 6])
  c = np.array([a, [7, 8, 9], b], order="F")
``` 

Would be translated to (focus on `c` `ndarray` creation):

```c
int main()
{
    t_ndarray a = {.shape = NULL};
    t_ndarray b = {.shape = NULL};
    t_ndarray c = {.shape = NULL};
    a = array_create(1, (int64_t[]){3}, nd_int64, false, order_c);
    int64_t array_dummy[] = {1, 2, 3};
    memcpy(a.nd_int64 + (a.current_length) , array_dummy, 3 * a.type_size);
    a.current_length += 3;
    b = array_create(1, (int64_t[]){3}, nd_int64, false, order_c);
    int64_t array_dummy_0001[] = {4, 5, 6};
    memcpy(b.nd_int64 + (b.current_length) , array_dummy_0001, 3 * b.type_size);
    b.current_length += 3;
    
    // 'c' ndarray creation
    
    c = array_create(2, (int64_t[]){3, 3}, nd_int64, false, order_f); // Allocating the required ndarray (order_f)
    t_ndarray temp_array = {.shape = NULL};
    temp_array = array_create(2, (int64_t[]){3, 3}, nd_int64, false, order_c); // Allocating a temp_array (order_c)
    array_copy_data(&temp_array, a); // Copying the first element to temp_array
    int64_t array_dummy_0002[] = {7, 8, 9};
    memcpy(temp_array.nd_int64 + (temp_array.current_length) , array_dummy_0002, 3 * temp_array.type_size); // Copying the second element to temp_array
    temp_array.current_length += 3;
    array_copy_data(&temp_array, b); // Copying the third element to temp_array
    array_copy_data(&c, temp_array); // Copying and transposing our temp_array to the requied ndarray 'c'
    free_array(temp_array); // freeing the temp_array
    free_array(a);
    free_array(b);
    free_array(c);
    return 0;
}
```

// TODO: alternative to current_length, use memcpy directly for order_c, array_copy_data should only be used when trying to transpose for now
