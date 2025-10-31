#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// ============================================================================
// TEST EXAMPLE 1: Wild Pointer Dereference Test
// ============================================================================

// BUG: Wild pointer dereference test
void test_wild_pointer() {
    // Test 1: Basic wild pointer dereference
    int *ptr1; // BUG: wild pointer dereference
    *ptr1 = 42;
    
    // Test 2: Struct pointer wild pointer
    struct Point {
        int x;
        int y;
    };
    struct Point *p; // BUG: wild pointer dereference
    p->x = 10;
    p->y = 20;
    
    // Test 3: Array pointer wild pointer
    int *arr_ptr; // BUG: wild pointer dereference
    arr_ptr[0] = 100;
    arr_ptr[1] = 200;
    
    // Test 4: String pointer wild pointer
    char *str_ptr; // BUG: wild pointer dereference
    str_ptr[0] = 'A';
    str_ptr[1] = 'B';
    
    // Test 5: Double pointer wild pointer
    int **double_ptr; // BUG: wild pointer dereference
    **double_ptr = 999;
    
    // Test 6: Function parameter wild pointer
    void test_wild_param(int *param) {
        *param = 123; // BUG: wild pointer dereference
    }
    int *wild_param; // BUG: wild pointer dereference
    test_wild_param(wild_param);
    
    // Test 7: Loop wild pointer
    int *loop_ptr; // BUG: wild pointer dereference
    for (int i = 0; i < 5; i++) {
        loop_ptr[i] = i * 10; // BUG: wild pointer dereference
    }
    
    // Test 8: Conditional statement wild pointer
    int *cond_ptr; // BUG: wild pointer dereference
    if (1) {
        *cond_ptr = 456; // BUG: wild pointer dereference
    }
    
    // Test 9: Nested struct wild pointer
    struct Nested {
        int value;
        struct Point *point_ptr;
    };
    struct Nested *nested_ptr; // BUG: wild pointer dereference
    nested_ptr->point_ptr->x = 30; // BUG: wild pointer dereference
    
    // Test 10: Function returned wild pointer
    int* get_wild_pointer() {
        int *local_ptr; // BUG: wild pointer dereference
        return local_ptr; // BUG: wild pointer dereference
    }
    int *returned_ptr = get_wild_pointer();
    *returned_ptr = 789; // BUG: wild pointer dereference
}

// ============================================================================
// TEST EXAMPLE 2: Memory Leak Detection
// ============================================================================

// Function 1: Function with memory leaks
void test_memory_leak() {
    // Allocate memory but not freed
    int *ptr1 = malloc(sizeof(int) * 10);
    char *str1 = malloc(100);
    double *arr1 = calloc(20, sizeof(double));
    
    // Use memory
    ptr1[0] = 42;
    strcpy(str1, "Hello World");
    arr1[0] = 3.14;
    
    // BUG: memory leak - forget to free memory
    printf("ptr1[0] = %d\n", ptr1[0]);
    printf("str1 = %s\n", str1);
    printf("arr1[0] = %f\n", arr1[0]);
}

// Function 2: Correctly free memory
void test_correct_free() {
    int *ptr2 = malloc(sizeof(int) * 5);
    char *str2 = malloc(50);
    
    if (ptr2 && str2) {
        ptr2[0] = 100;
        strcpy(str2, "Correct");
        
        printf("ptr2[0] = %d\n", ptr2[0]);
        printf("str2 = %s\n", str2);
        
        // Correctly free memory - should not report error
        free(ptr2);
        free(str2);
    }
}

// Function 3: Partial memory leak
void test_partial_leak() {
    int *ptr3 = malloc(sizeof(int) * 3);
    char *str3 = malloc(30);
    float *arr3 = malloc(sizeof(float) * 5);
    
    if (ptr3) {
        ptr3[0] = 200;
        free(ptr3); // Correctly freed
    }
    
    if (str3) {
        strcpy(str3, "Partial");
        // BUG: memory leak - forget to free str3
    }
    
    if (arr3) {
        arr3[0] = 2.5;
        free(arr3); // Correctly freed
    }
}

// Function 4: Using realloc
void test_realloc_leak() {
    int *ptr4 = malloc(sizeof(int) * 10);
    if (ptr4) {
        ptr4[0] = 300;
        
        // Reallocate memory
        ptr4 = realloc(ptr4, sizeof(int) * 20);
        if (ptr4) {
            ptr4[10] = 400;
            // BUG: memory leak - forget to free reallocated memory
        }
    }
}

// Function 5: Memory leak in nested function call
void helper_function() {
    char *temp = malloc(20);
    if (temp) {
        strcpy(temp, "Helper");
        // BUG: memory leak - allocated in helper function but not freed
    }
}

void test_nested_leak() {
    int *ptr5 = malloc(sizeof(int) * 2);
    if (ptr5) {
        ptr5[0] = 500;
        free(ptr5); // Correctly freed
        
        // Call helper function with memory leak
        helper_function();
    }
}

// Function 6: Conditional free
void test_conditional_free() {
    int *ptr6 = malloc(sizeof(int) * 4);
    char *str6 = malloc(40);
    
    if (ptr6 && str6) {
        ptr6[0] = 600;
        strcpy(str6, "Conditional");
        
        // Only free under certain conditions
        if (ptr6[0] > 500) {
            free(ptr6); // Correctly freed
        }
        // BUG: memory leak - str6 not freed under certain conditions
    }
}

// ============================================================================
// TEST EXAMPLE 3: Struct Pointer and Variable Declaration Recognition
// ============================================================================

// Define test structs
struct TestPoint {
    int x;
    int y;
};

struct TestNode {
    int data;
    struct TestNode* next;
};

struct TestGraph {
    int vertices;
    struct TestNode** adjList;
};

// Test various struct pointer declaration methods
void test_struct_pointer_declarations() {
    // Test different struct pointer declaration syntax
    struct TestPoint* p1;           // Standard syntax
    struct TestPoint *p2;           // Asterisk near variable name
    struct TestPoint * p3;          // Asterisk with spaces on both sides
    struct TestPoint*p4;            // Asterisk attached to type name
    
    // Test struct variable declaration
    struct TestPoint point1;        // Standard struct variable
    struct TestPoint point2 = {0};  // Initialized struct variable
    
    // Test array declarations
    struct TestPoint points[10];    // Struct array
    struct TestPoint* ptr_array[5]; // Struct pointer array
    
    // Test nested structs
    struct TestNode node1;
    struct TestNode* node_ptr;
    
    // Test complex structs
    struct TestGraph graph1;
    struct TestGraph* graph_ptr;
    
    // Test typedef struct (if supported)
    typedef struct {
        int id;
        char name[50];
    } Student;
    
    Student student1;
    Student* student_ptr;
    
    // Test uninitialized use - should be detected
    p1->x = 10;        // BUG: wild pointer dereference
    p2->y = 20;        // BUG: wild pointer dereference
    p3->x = 30;        // BUG: wild pointer dereference
    p4->y = 40;        // BUG: wild pointer dereference
    
    // Test struct member access
    point1.x = 100;    // Correct: access struct variable member
    point1.y = 200;    // Correct: access struct variable member
    
    // Test array access
    points[0].x = 1;   // Correct: access struct array element
    points[0].y = 2;   // Correct: access struct array element
    
    // Test pointer array
    ptr_array[0] = p1; // Assign uninitialized pointer to array
    
    // Test nested struct access
    node1.data = 42;   // Correct: access nested struct member
    node_ptr->data = 43; // BUG: wild pointer dereference
    
    // Test complex struct access
    graph1.vertices = 5; // Correct: access complex struct member
    graph_ptr->vertices = 6; // BUG: wild pointer dereference
    
    // Test typedef struct access
    student1.id = 1;   // Correct: access typedef struct member
    student_ptr->id = 2; // BUG: wild pointer dereference
}

// ============================================================================
// TEST EXAMPLE 4: Wild Pointer and Null Pointer Detection
// ============================================================================

// Function 1: Wild pointer dereference
void test_wild_pointer_example4() {
    int *ptr1; // Uninitialized pointer
    *ptr1 = 42; // BUG: wild pointer dereference
    
    char *str1; // Uninitialized pointer
    str1[0] = 'A'; // BUG: wild pointer dereference
    
    double *arr1; // Uninitialized pointer
    arr1[0] = 3.14; // BUG: wild pointer dereference
}

// Function 2: Null pointer dereference
void test_null_pointer() {
    int *ptr2 = NULL; // Initialize to NULL
    *ptr2 = 100; // BUG: null pointer dereference
    
    char *str2 = 0; // Initialize to 0 (equivalent to NULL)
    str2[0] = 'B'; // BUG: null pointer dereference
    
    float *arr2 = NULL;
    arr2[0] = 2.5; // BUG: null pointer dereference
}

// Function 3: Wild pointer as function parameter
void test_wild_pointer_param() {
    int *ptr3; // Uninitialized pointer
    printf("%d\n", *ptr3); // BUG: wild pointer dereference
    
    char *str3; // Uninitialized pointer
    scanf("%s", str3); // BUG: wild pointer dereference
}

// Function 4: Null pointer as function parameter
void test_null_pointer_param() {
    int *ptr4 = NULL;
    printf("%d\n", *ptr4); // BUG: null pointer dereference
    
    char *str4 = 0;
    scanf("%s", str4); // BUG: null pointer dereference
}

// Function 5: Correct pointer usage (should not report error)
void test_correct_pointer() {
    int x = 42;
    int *ptr5 = &x; // Correct: point to valid variable
    printf("%d\n", *ptr5); // Correct: dereference valid pointer
    
    char str5[10] = "Hello";
    char *ptr6 = str5; // Correct: point to array
    printf("%s\n", ptr6); // Correct: use valid pointer
    
    int *ptr7 = malloc(sizeof(int)); // Correct: allocate memory
    if (ptr7) {
        *ptr7 = 100; // Correct: dereference valid pointer
        printf("%d\n", *ptr7);
        free(ptr7); // Correct: free memory
    }
}

// ============================================================================
// TEST EXAMPLE 5: Printf and Scanf Format String Issues
// ============================================================================

void test_printf_scanf_format() {
    // Test 1: printf format string parameter count mismatch
    int a = 10;
    int b = 20;
    printf("%d %d %d\n", a, b); // BUG: format mismatch - format string has 3 %d but only 2 parameters
    
    // Test 2: printf format string parameter type mismatch
    int c = 30;
    float d = 3.14f;
    char e = 'A';
    printf("%d %f %c %s\n", c, d, e); // BUG: format mismatch - format string has %s but no string parameter
    
    // Test 3: printf parameter count more than format string
    int f = 40;
    int g = 50;
    printf("%d\n", f, g); // BUG: format mismatch - format string only has 1 %d but 2 parameters
}

// ============================================================================
// TEST EXAMPLE 6: Infinite Loop Test
// ============================================================================

void test_infinite_loops() {
    // Test 1: Basic infinite loop for(;;)
    printf("Test 1: Basic infinite loop\n");
    for(;;) { // BUG: infinite loop
        printf("infinite for loop\n");
    }
    
    // Test 2: while(1) infinite loop
    printf("Test 2: while(1) infinite loop\n");
    while(1) { // BUG: infinite loop
        printf("infinite while loop\n");
    }
    
    // Test 3: Loop condition always true
    printf("Test 3: Loop condition always true\n");
    int flag = 1;
    while(flag) { // BUG: infinite loop
        printf("flag is always true\n");
        // Forgot to modify flag
    }
    
    // Test 4: Loop variable never satisfies exit condition
    printf("Test 4: Loop variable never satisfies exit condition\n");
    for(int i = 10; i >= 10; i++) { // BUG: infinite loop
        printf("i = %d\n", i);
    }
    
    // Test 5: Loop variable decrements but condition is wrong
    printf("Test 5: Loop variable decrements but condition is wrong\n");
    for(int j = 0; j < 10; j--) { // BUG: infinite loop
        printf("j = %d\n", j);
    }
    
    // Test 6: Loop variable step too large
    printf("Test 6: Loop variable step too large\n");
    for(int k = 0; k == 10; k += 3) { // BUG: infinite loop
        printf("k = %d\n", k);
    }
    
    // Test 7: Loop variable incorrectly modified in loop body
    printf("Test 7: Loop variable incorrectly modified in loop body\n");
    int m = 0;
    while(m < 10) { // BUG: infinite loop
        printf("m = %d\n", m);
        m = m; // No actual change
    }
    
    // Test 8: Infinite loop in nested loop
    printf("Test 8: Infinite loop in nested loop\n");
    for(int outer = 0; outer < 5; outer++) {
        for(int inner = 0; inner < 3; inner++) {
            printf("outer=%d, inner=%d\n", outer, inner);
            // Inner loop has no proper exit condition
            if (inner == 2) {
                inner = 0; // BUG: infinite loop
            }
        }
    }
    
    // Test 9: Float loop precision problem
    printf("Test 9: Float loop precision problem\n");
    for(float f = 0.0f; f != 1.0f; f += 0.1f) { // BUG: infinite loop
        printf("f = %f\n", f);
    }
    
    // Test 10: Loop condition depends on external variable but external variable doesn't change
    printf("Test 10: Loop condition depends on external variable\n");
    int counter = 0;
    while(counter < 100) { // BUG: infinite loop
        printf("counter = %d\n", counter);
        // Forgot to increment counter
    }
    
    // Test 11: break statement never executes
    printf("Test 11: break statement never executes\n");
    int n = 0;
    while(1) { // BUG: infinite loop
        printf("n = %d\n", n);
        n++;
        if (n < 0) { // This condition will never be true
            break;
        }
    }
    
    // Test 12: continue statement causes infinite loop
    printf("Test 12: continue statement causes infinite loop\n");
    int p = 0;
    while(p < 10) { // BUG: infinite loop
        if (p % 2 == 0) {
            continue; // Skip following p++, causing p to never change
        }
        p++;
    }
}

// ============================================================================
// TEST EXAMPLE 7: Use-After-Free Test
// ============================================================================

void test_use_after_free() {
    // Test 1: Basic use-after-free
    int *ptr1 = malloc(sizeof(int));
    *ptr1 = 42;
    free(ptr1);
    printf("%d\n", *ptr1); // BUG: use-after-free
    
    // Test 2: Use-after-free in loop
    int *ptr2 = malloc(sizeof(int) * 10);
    for (int i = 0; i < 10; i++) {
        ptr2[i] = i;
    }
    free(ptr2);
    for (int i = 0; i < 10; i++) {
        printf("%d\n", ptr2[i]); // BUG: use-after-free
    }
    
    // Test 3: Use-after-free with reassignment
    int *ptr3 = malloc(sizeof(int));
    *ptr3 = 100;
    free(ptr3);
    *ptr3 = 200; // BUG: use-after-free
    
    // Test 4: Use-after-free in conditional
    int *ptr4 = malloc(sizeof(int));
    *ptr4 = 300;
    free(ptr4);
    if (*ptr4 > 0) { // BUG: use-after-free
        printf("ptr4 is positive\n");
    }
    
    // Test 5: Double free
    int *ptr5 = malloc(sizeof(int));
    *ptr5 = 400;
    free(ptr5);
    free(ptr5); // BUG: double free
}

// ============================================================================
// MAIN FUNCTION
// ============================================================================

int main() {
    printf("=== COMPREHENSIVE C BUG DETECTION TEST ===\n\n");
    
    printf("Testing wild pointer dereference...\n");
    test_wild_pointer();
    
    printf("\nTesting memory leak detection...\n");
    test_memory_leak();
    test_correct_free();
    test_partial_leak();
    test_realloc_leak();
    test_nested_leak();
    test_conditional_free();
    
    printf("\nTesting struct pointer and variable declaration recognition...\n");
    test_struct_pointer_declarations();
    
    printf("\nTesting wild pointer and null pointer detection...\n");
    test_wild_pointer_example4();
    test_null_pointer();
    test_wild_pointer_param();
    test_null_pointer_param();
    test_correct_pointer();
    
    printf("\nTesting printf and scanf format string issues...\n");
    test_printf_scanf_format();
    
    printf("\nTesting infinite loops...\n");
    test_infinite_loops();
    
    printf("\nTesting use-after-free...\n");
    test_use_after_free();
    
    printf("\n=== ALL TESTS COMPLETED ===\n");
    
    return 0;
}
