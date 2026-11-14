RUNNABLE_WRAPPERS = {
    "encapsulation": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        BankAccount account = new BankAccount();\n"
        "        account.deposit(250);\n"
        "        System.out.println(account.balanceCents());\n"
        "    }\n"
        "}"
    ),
    "this-static-final": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(new Circle(2).area());\n"
        "    }\n"
        "}"
    ),
    "composition": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        new Car(new Engine()).start();\n"
        "    }\n"
        "}"
    ),
    "inheritance": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        '        System.out.println(new Manager("Ari").name());\n'
        "    }\n"
        "}"
    ),
    "overriding-polymorphism": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        Shape shape = new Square(4);\n"
        "        System.out.println(shape.area());\n"
        "    }\n"
        "}"
    ),
    "abstract-classes": (
        "class PlainReport extends Report {\n"
        "    @Override void writeContent() { System.out.println(\"Report content\"); }\n"
        "}\n\n"
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        new PlainReport().print();\n"
        "    }\n"
        "}"
    ),
    "interfaces": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        Payable invoice = new Invoice(1250);\n"
        "        System.out.println(invoice.amountCents());\n"
        "    }\n"
        "}"
    ),
    "equality": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(new Point(2, 3).equals(new Point(2, 3)));\n"
        "    }\n"
        "}"
    ),
    "exceptions": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        try {\n"
        '            System.out.println(ScoreParser.parseScore("invalid"));\n'
        "        } catch (IllegalArgumentException error) {\n"
        "            System.out.println(error.getMessage());\n"
        "        }\n"
        "    }\n"
        "}"
    ),
    "solid": (
        "class ConsoleNotifier implements Notifier {\n"
        "    public void send(String recipient, String message) {\n"
        '        System.out.println(recipient + ": " + message);\n'
        "    }\n"
        "}\n\n"
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        '        new ReminderService(new ConsoleNotifier()).remind("Ari");\n'
        "    }\n"
        "}"
    ),
    "design-patterns": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(new Checkout().total(500, new NoDiscount()));\n"
        "    }\n"
        "}"
    ),
    "capstone": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        Library library = new Library();\n"
        '        library.add("978-1", "Java Design");\n'
        '        System.out.println(library.findTitle("978-1"));\n'
        "    }\n"
        "}"
    ),
}


def _lesson(slug, title, level, summary, body, example, exercise, hint, quiz):
    if slug in RUNNABLE_WRAPPERS:
        example = f"{example}\n\n{RUNNABLE_WRAPPERS[slug]}"
    return {
        "slug": f"java-{slug}",
        "track": "Java",
        "language": "Java",
        "title": title,
        "level": level,
        "summary": summary,
        "body": body,
        "example": example,
        "exercise": exercise,
        "hint": hint,
        "quiz": quiz,
    }


JAVA_LESSONS = [
    _lesson(
        "setup",
        "Install Java and set up your tools",
        "Start here",
        "Understand the JDK, compiler, runtime, and ways to run Java.",
        "The Java Development Kit (JDK) includes tools such as javac and java. "
        "javac compiles source into bytecode; the Java Virtual Machine (JVM) runs "
        "that bytecode. Check java --version and javac --version, then use an IDE "
        "or a terminal to build a small project.",
        'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Java is ready!");\n    }\n}',
        "Install a current JDK and confirm both java --version and javac --version work.",
        "The runtime command is java; the compiler command is javac.",
        "Which JDK tool compiles a .java source file?",
    ),
    _lesson(
        "first-program",
        "Your first Java program",
        "Start here",
        "Run a class with a main method and print a message.",
        "A Java application can start in a main method. The public class name must "
        "match its file name, so Main belongs in Main.java. System.out.println "
        "writes a line to standard output, and Java statements end with semicolons.",
        'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, Java!");\n    }\n}',
        "Change the message and run Main.java.",
        "Keep the class named Main when the file is named Main.java.",
        "What method is the conventional entry point for a Java application?",
    ),
    _lesson(
        "variables-and-types",
        "Variables, types, and values",
        "Beginner",
        "Declare strongly typed variables and choose suitable primitive or reference types.",
        "Java is statically typed: a variable has a declared type. Common primitives "
        "include int, long, double, boolean, and char. String is a reference type. "
        "Use var only for a local variable whose initializer makes its type clear; "
        "it does not make Java dynamically typed.",
        'public class Main {\n    public static void main(String[] args) {\n        String learner = "Ari";\n        int lessons = 3;\n        boolean practicing = true;\n        System.out.println(learner + " completed " + lessons + ": " + practicing);\n    }\n}',
        "Store a course title, lesson count, and completion state in appropriately typed variables.",
        "Text uses String; a whole-number count commonly uses int.",
        "Is Java's var keyword dynamic typing or local type inference?",
    ),
    _lesson(
        "operators",
        "Operators and expressions",
        "Beginner",
        "Calculate with arithmetic, comparison, and logical operators.",
        "Arithmetic operators include +, -, *, /, and %. Integer division discards "
        "the fractional part. Comparisons such as >= produce booleans; &&, ||, and "
        "! combine or invert conditions. Parentheses make precedence easier to read.",
        'public class Main {\n    public static void main(String[] args) {\n        int minutes = 137;\n        System.out.println(minutes / 60 + "h " + minutes % 60 + "m");\n    }\n}',
        "Convert a number of minutes into whole hours and remaining minutes.",
        "Use integer division for hours and the remainder operator for minutes.",
        "What does the % operator return for two integers?",
    ),
    _lesson(
        "strings",
        "Strings and text",
        "Beginner",
        "Create, compare, and format immutable String values.",
        "String objects are immutable: methods such as trim and toUpperCase return "
        "new strings. Use equals to compare string contents; == compares object "
        "references. StringBuilder is useful when repeatedly building text in a loop.",
        'public class Main {\n    public static void main(String[] args) {\n        String name = "  ada  ".trim();\n        System.out.println("Hello, " + name.substring(0, 1).toUpperCase() + name.substring(1));\n    }\n}',
        "Normalize a name by trimming whitespace and displaying a greeting.",
        "Use equals for content comparisons and remember that trim returns a string.",
        "Which method compares two strings by their contents?",
    ),
    _lesson(
        "input-output",
        "Console input and formatted output",
        "Beginner",
        "Read simple input with Scanner and display useful output.",
        "Scanner can read tokens or full lines from System.in. nextInt reads an "
        "integer; nextLine reads the rest of the current line. After nextInt, "
        "consume its trailing newline before reading a full line. For small examples, "
        "avoid closing a Scanner that wraps System.in before the program is done.",
        'import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner input = new Scanner(System.in);\n        String name = input.nextLine();\n        System.out.println("Welcome, " + name + "!");\n    }\n}',
        "Read a learner's name and print a personalized welcome.",
        "Construct Scanner with System.in and use nextLine for text with spaces.",
        "Which Scanner method reads an entire line of text?",
    ),
    _lesson(
        "conditionals",
        "Make decisions with conditionals",
        "Beginner",
        "Branch with if, else if, else, and switch.",
        "An if statement runs a block when its boolean condition is true. else if "
        "checks another condition, and else handles the remaining case. Use switch "
        "when one value selects among several cases; include a default for unexpected "
        "values when appropriate.",
        'public class Main {\n    public static void main(String[] args) {\n        int score = 82;\n        if (score >= 90) System.out.println("Excellent");\n        else if (score >= 70) System.out.println("Pass");\n        else System.out.println("Keep practicing");\n    }\n}',
        "Classify a score as excellent, passing, or needing more practice.",
        "Check the highest threshold first so a high score is not caught by a lower one.",
        "What type of result must an if condition produce?",
    ),
    _lesson(
        "loops",
        "Repeat work with loops",
        "Beginner",
        "Use for, enhanced for, and while loops to repeat tasks.",
        "A for loop is useful when a counter or range is known. The enhanced for "
        "loop visits each element in an array or collection. A while loop repeats "
        "while its condition remains true; update the state that controls it to avoid "
        "an accidental infinite loop.",
        'public class Main {\n    public static void main(String[] args) {\n        for (int number = 1; number <= 5; number++) {\n            System.out.println(number);\n        }\n    }\n}',
        "Print the numbers from 1 through 5, then try printing only even numbers.",
        "The loop condition is checked before each iteration.",
        "When does a while loop stop running?",
    ),
    _lesson(
        "methods",
        "Methods, parameters, and return values",
        "Beginner",
        "Create reusable behavior with method parameters and return types.",
        "A method signature includes its name and parameter types. A void method "
        "does not return a value; other methods declare a return type and use return "
        "to send a result to the caller. Parameters are local to the method.",
        'public class Main {\n    static int doubleValue(int number) {\n        return number * 2;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(doubleValue(6));\n    }\n}',
        "Write a method that converts a temperature in Celsius to Fahrenheit.",
        "Return the calculation instead of printing it inside the conversion method.",
        "Which keyword declares that a method returns no value?",
    ),
    _lesson(
        "arrays",
        "Arrays and indexed data",
        "Beginner",
        "Store a fixed-size sequence and visit it safely.",
        "An array has a fixed length and uses zero-based indexes. Read its length "
        "with array.length, not a method call. An enhanced for loop is convenient "
        "when you need each value but do not need its index.",
        'public class Main {\n    public static void main(String[] args) {\n        int[] scores = {80, 95, 72};\n        int total = 0;\n        for (int score : scores) total += score;\n        System.out.println(total / scores.length);\n    }\n}',
        "Calculate the total and average of a small array of scores.",
        "Indexes range from 0 to length - 1; use an enhanced for loop for a total.",
        "What is the index of the first element in a Java array?",
    ),
    _lesson(
        "lists",
        "Resizable lists and collection basics",
        "Beginner",
        "Use ArrayList when a sequence needs to grow or shrink.",
        "An array has a fixed length; ArrayList is a resizable List implementation. "
        "Use a generic type such as List<String> to describe its elements. add "
        "appends, get reads an indexed value, and size returns the current element count.",
        'import java.util.ArrayList;\nimport java.util.List;\n\npublic class Main {\n    public static void main(String[] args) {\n        List<String> topics = new ArrayList<>();\n        topics.add("classes");\n        topics.add("objects");\n        System.out.println(topics.size());\n    }\n}',
        "Create a list of three learning topics and print each one.",
        "Declare against the List interface and create an ArrayList instance.",
        "Which method returns the number of items currently in a List?",
    ),
    _lesson(
        "classes-and-objects",
        "Classes and objects",
        "Beginner",
        "Model a concept with a class, fields, and instance methods.",
        "A class defines a type and the state and behavior its objects can have. "
        "Each object is an instance with its own instance fields. Create an object "
        "with new, then call its public methods through the reference.",
        'class Counter {\n    private int value;\n\n    void increment() {\n        value++;\n    }\n\n    int getValue() {\n        return value;\n    }\n}\n\npublic class Main {\n    public static void main(String[] args) {\n        Counter counter = new Counter();\n        counter.increment();\n        System.out.println(counter.getValue());\n    }\n}',
        "Create a Book class with a title field and a method that displays the title.",
        "Put state and behavior that belong together in the same class.",
        "What does new Counter() create?",
    ),
    _lesson(
        "constructors",
        "Constructors and valid object state",
        "Beginner",
        "Initialize objects with constructors and validate their starting state.",
        "A constructor has the same name as its class and no return type. It can "
        "require values needed to create a valid object. Use this.field when a "
        "parameter has the same name as an instance field.",
        'class Book {\n    private final String title;\n\n    Book(String title) {\n        this.title = title;\n    }\n\n    String title() {\n        return title;\n    }\n}\n\npublic class Main {\n    public static void main(String[] args) {\n        System.out.println(new Book("Dune").title());\n    }\n}',
        "Add a constructor that requires a nonblank title for a Book.",
        "A constructor has no declared return type; use this to refer to the field.",
        "How is a constructor named relative to its class?",
    ),
    _lesson(
        "encapsulation",
        "Encapsulation and access control",
        "Beginner",
        "Protect object invariants by controlling how state can change.",
        "Encapsulation keeps implementation details behind a small public API. "
        "private fields prevent callers from changing state arbitrarily. Methods "
        "can validate changes so an object cannot enter an invalid state. Avoid "
        "adding getters and setters automatically when a behavior-focused method is clearer.",
        'class BankAccount {\n    private int balanceCents;\n\n    void deposit(int cents) {\n        if (cents <= 0) throw new IllegalArgumentException("Deposit must be positive");\n        balanceCents += cents;\n    }\n\n    int balanceCents() {\n        return balanceCents;\n    }\n}',
        "Add a withdrawal method that rejects an amount larger than the balance.",
        "Keep the balance private and validate an operation before changing it.",
        "What design benefit does private state provide?",
    ),
    _lesson(
        "this-static-final",
        "this, static, and final",
        "Beginner",
        "Distinguish object state from class-level members and constants.",
        "this refers to the current object. An instance field belongs to each object; "
        "a static field belongs to the class. final prevents reassignment of a "
        "variable, and a static final field is commonly used for a constant. A "
        "final reference cannot point elsewhere, though the referenced object may still be mutable.",
        'class Circle {\n    static final double PI = 3.141592653589793;\n    private final double radius;\n\n    Circle(double radius) {\n        this.radius = radius;\n    }\n\n    double area() {\n        return PI * radius * radius;\n    }\n}',
        "Add a final field for a circle's radius and an area method.",
        "Use static for a value shared by all instances and final for a value set once.",
        "Does a static field belong to each object or to the class?",
    ),
    _lesson(
        "composition",
        "Composition and object collaboration",
        "Intermediate",
        "Build behavior by giving an object collaborators it can use.",
        "Composition models a has-a relationship: one object stores or receives "
        "another object and delegates work to it. It keeps responsibilities focused "
        "and often allows behavior to change without creating a deep inheritance "
        "tree. Prefer constructor injection for required collaborators.",
        'class Engine {\n    void start() { System.out.println("Engine started"); }\n}\n\nclass Car {\n    private final Engine engine;\n\n    Car(Engine engine) { this.engine = engine; }\n    void start() { engine.start(); }\n}',
        "Model a library that contains a collection of Book objects.",
        "A Library has Books; it is not a specialized kind of Book.",
        "What relationship does composition usually model?",
    ),
    _lesson(
        "inheritance",
        "Inheritance and subtyping",
        "Intermediate",
        "Use inheritance when a genuine subtype relationship exists.",
        "A subclass extends a superclass and can reuse accessible behavior. In "
        "Java, a class has one direct superclass. Inheritance is appropriate only "
        "when the subtype can honor the promises of the base type; use composition "
        "when the relationship is merely code reuse.",
        'class Employee {\n    private final String name;\n    Employee(String name) { this.name = name; }\n    String name() { return name; }\n}\n\nclass Manager extends Employee {\n    Manager(String name) { super(name); }\n}',
        "Create a specialized type only if it can be used wherever its base type is expected.",
        "Call super(...) to initialize the superclass portion of the object.",
        "Which keyword declares that a class inherits from another class?",
    ),
    _lesson(
        "overriding-polymorphism",
        "Overriding, dynamic dispatch, and polymorphism",
        "Intermediate",
        "Write interchangeable implementations behind a shared parent type.",
        "A subclass overrides an instance method with the same compatible signature. "
        "Use @Override so the compiler checks your intent. When a method is called "
        "through a base-type reference, Java selects the implementation for the "
        "object's runtime class; this is dynamic dispatch.",
        'class Shape {\n    double area() { return 0; }\n}\n\nclass Square extends Shape {\n    private final double side;\n    Square(double side) { this.side = side; }\n    @Override double area() { return side * side; }\n}',
        "Store different Shape objects in a list and total their areas through the common type.",
        "The declared reference type controls available methods; the object type selects an override.",
        "Which method implementation runs when an overridden method is called?",
    ),
    _lesson(
        "abstract-classes",
        "Abstract classes and template behavior",
        "Intermediate",
        "Share common state and behavior while requiring subclasses to fill in details.",
        "An abstract class cannot be instantiated directly. It can contain fields, "
        "constructors, implemented methods, and abstract methods. A concrete "
        "subclass must implement inherited abstract methods. Use an abstract class "
        "when related types share meaningful state or implementation.",
        'abstract class Report {\n    final void print() {\n        open();\n        writeContent();\n        close();\n    }\n    abstract void writeContent();\n    void open() { System.out.println("Start"); }\n    void close() { System.out.println("End"); }\n}',
        "Create a concrete report type that supplies its own writeContent behavior.",
        "An abstract method has no body and must be implemented by a concrete subclass.",
        "Can an abstract class be instantiated directly?",
    ),
    _lesson(
        "interfaces",
        "Interfaces and capability-based design",
        "Intermediate",
        "Define contracts that unrelated classes can implement.",
        "An interface describes behavior a type promises to provide. A class can "
        "implement multiple interfaces, which supports capabilities without "
        "multiple class inheritance. Keep interfaces focused; use default methods "
        "sparingly when a shared implementation is genuinely part of the contract.",
        'interface Payable {\n    int amountCents();\n}\n\nclass Invoice implements Payable {\n    private final int amount;\n    Invoice(int amount) { this.amount = amount; }\n    public int amountCents() { return amount; }\n}',
        "Define a Describable interface and implement it for two unrelated types.",
        "An implementing class must provide the interface's required methods.",
        "How many classes can one Java class directly extend?",
    ),
    _lesson(
        "enums-and-records",
        "Enums, records, and data modeling",
        "Intermediate",
        "Represent fixed choices and transparent immutable data clearly.",
        "An enum defines a closed set of named constants and can include fields "
        "and methods. A record is a concise data carrier with final components, "
        "accessors, and value-based equals and hashCode. Use a regular class when "
        "the type needs mutable state or more complex identity.",
        'enum Status { NEW, IN_PROGRESS, COMPLETE }\n\nrecord LessonResult(String title, int score) {}\n\npublic class Main {\n    public static void main(String[] args) {\n        LessonResult result = new LessonResult("Classes", 95);\n        System.out.println(result.title() + ": " + result.score());\n    }\n}',
        "Represent a fixed order status with an enum and a simple result with a record.",
        "Use an enum for a closed set of values; records suit simple value data.",
        "What kind of value set is an enum designed to represent?",
    ),
    _lesson(
        "equality",
        "Object equality, equals, and hashCode",
        "Intermediate",
        "Define value equality correctly for classes used in collections.",
        "The default Object.equals compares identity. Override equals to compare "
        "meaningful state when the type has value semantics, and override hashCode "
        "consistently: equal objects must have equal hash codes. Hash-based "
        "collections rely on this contract. Records implement value equality for their components.",
        'import java.util.Objects;\n\nclass Point {\n    private final int x;\n    private final int y;\n    Point(int x, int y) { this.x = x; this.y = y; }\n    @Override public boolean equals(Object other) {\n        if (!(other instanceof Point point)) return false;\n        return x == point.x && y == point.y;\n    }\n    @Override public int hashCode() { return Objects.hash(x, y); }\n}',
        "Implement value equality for a small immutable type and test equal instances.",
        "Override equals and hashCode together, using the same state in both.",
        "What must be true about the hash codes of two equal objects?",
    ),
    _lesson(
        "generics",
        "Generics and type-safe abstractions",
        "Intermediate",
        "Parameterize classes and methods so they work safely with different types.",
        "Generics let a class, interface, or method work with a type parameter. "
        "List<String> communicates its element type and avoids casts. Type erasure "
        "means most generic type information is not available at runtime. Use "
        "bounded type parameters when an operation requires a capability.",
        'class Box<T> {\n    private final T value;\n    Box(T value) { this.value = value; }\n    T value() { return value; }\n}\n\npublic class Main {\n    public static void main(String[] args) {\n        Box<String> box = new Box<>("Java");\n        System.out.println(box.value().toUpperCase());\n    }\n}',
        "Create a generic Pair<T, U> that stores and returns two values.",
        "Use type parameters instead of Object so callers retain compile-time type safety.",
        "What does the T represent in a declaration such as Box<T>?",
    ),
    _lesson(
        "maps-and-sets",
        "Maps, sets, and collection choices",
        "Intermediate",
        "Choose collections based on lookup, uniqueness, and ordering needs.",
        "A Map associates keys with values; a Set stores unique elements. HashMap "
        "and HashSet offer expected constant-time basic operations when hashCode "
        "and equals are consistent. Choose LinkedHashMap to preserve insertion "
        "order or TreeMap when sorted keys are required.",
        'import java.util.HashMap;\nimport java.util.Map;\n\npublic class Main {\n    public static void main(String[] args) {\n        Map<String, Integer> counts = new HashMap<>();\n        counts.merge("Java", 1, Integer::sum);\n        counts.merge("Java", 1, Integer::sum);\n        System.out.println(counts.get("Java"));\n    }\n}',
        "Count repeated words in a map and keep unique tags in a set.",
        "Use a Map when each key needs an associated value.",
        "What does a Set guarantee about its elements?",
    ),
    _lesson(
        "exceptions",
        "Exceptions and failure handling",
        "Intermediate",
        "Handle expected failures without hiding programming errors.",
        "An exception interrupts normal control flow. Catch an exception only "
        "when you can recover, add useful context, or translate it at a boundary. "
        "Checked exceptions must be caught or declared; unchecked exceptions often "
        "signal invalid arguments or programming errors. Avoid catching Exception "
        "just to ignore it.",
        'class ScoreParser {\n    static int parseScore(String text) {\n        try {\n            return Integer.parseInt(text);\n        } catch (NumberFormatException error) {\n            throw new IllegalArgumentException("Score must be a whole number", error);\n        }\n    }\n}',
        "Parse user input and report invalid values with a meaningful message.",
        "Catch the specific exception you expect and preserve its cause when wrapping it.",
        "Why should code usually catch a specific exception instead of Exception?",
    ),
    _lesson(
        "files-and-resources",
        "Files, paths, and try-with-resources",
        "Intermediate",
        "Read and write text files while ensuring resources are closed.",
        "Use Path and Files from java.nio.file for modern file operations. "
        "try-with-resources closes resources automatically, even when an exception "
        "occurs. Handle IOException at a boundary where the application can explain "
        "the failure. Never deserialize untrusted Java object streams.",
        'import java.io.IOException;\nimport java.nio.file.Files;\nimport java.nio.file.Path;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n        Path file = Path.of("notes.txt");\n        Files.writeString(file, "Practice composition");\n        System.out.println(Files.readString(file));\n    }\n}',
        "Save and load a small text file using Path and Files.",
        "Use try-with-resources for closeable streams; Files helpers manage their own resources.",
        "What problem does try-with-resources solve?",
    ),
    _lesson(
        "lambdas",
        "Lambdas and functional interfaces",
        "Intermediate",
        "Pass behavior as a value with lambdas and standard functional interfaces.",
        "A functional interface has one abstract method and can be implemented "
        "with a lambda. Java provides Predicate, Function, Consumer, and Supplier "
        "for common shapes of behavior. A lambda can capture local variables only "
        "when they are final or effectively final.",
        'import java.util.function.Predicate;\n\npublic class Main {\n    public static void main(String[] args) {\n        Predicate<String> isLong = text -> text.length() >= 5;\n        System.out.println(isLong.test("Java"));\n    }\n}',
        "Create a Predicate that checks whether a score meets a pass threshold.",
        "Match the lambda's input and return value to the functional interface method.",
        "How many abstract methods does a functional interface have?",
    ),
    _lesson(
        "streams",
        "Streams and data pipelines",
        "Intermediate",
        "Transform and aggregate collections with readable stream pipelines.",
        "A stream pipeline has a source, intermediate operations, and a terminal "
        "operation. filter and map are lazy intermediate operations; collect, count, "
        "and reduce are terminal operations. Streams do not store data and should "
        "not usually be reused after a terminal operation.",
        'import java.util.List;\n\npublic class Main {\n    public static void main(String[] args) {\n        List<Integer> scores = List.of(55, 82, 91);\n        int passed = scores.stream().filter(score -> score >= 70).count();\n        System.out.println(passed);\n    }\n}',
        "Filter passing scores and produce a list of their display labels.",
        "Use filter to select values, map to transform them, and a terminal operation to finish.",
        "Which kind of stream operation triggers execution of a pipeline?",
    ),
    _lesson(
        "optional",
        "Optional and explicit absence",
        "Intermediate",
        "Represent a possibly missing result without returning null.",
        "Optional<T> represents a value that may be absent, especially as a return "
        "type. Use map, orElseGet, or ifPresent to work with it. Avoid calling "
        "get without checking and avoid using Optional for every field or method parameter.",
        'import java.util.Optional;\n\npublic class Main {\n    static Optional<String> findNickname(String name) {\n        return name.equals("Ari") ? Optional.of("Ace") : Optional.empty();\n    }\n    public static void main(String[] args) {\n        System.out.println(findNickname("Ari").orElse("Learner"));\n    }\n}',
        "Return an Optional from a lookup and choose a fallback when no value exists.",
        "Use orElseGet when calculating the fallback is expensive.",
        "What does Optional.empty() represent?",
    ),
    _lesson(
        "testing",
        "Unit testing with JUnit",
        "Intermediate",
        "Test observable behavior with focused, repeatable unit tests.",
        "A unit test checks a small behavior in isolation. JUnit 5 uses annotations "
        "such as @Test and assertions such as assertEquals. Include ordinary, "
        "boundary, and invalid-input cases. Tests should be deterministic and "
        "should not depend on execution order.",
        'public class Main {\n    static int add(int left, int right) { return left + right; }\n    public static void main(String[] args) {\n        if (add(2, 3) != 5) throw new AssertionError("addition failed");\n        System.out.println("All checks passed");\n    }\n}',
        "Write tests for a method that validates and adds two amounts.",
        "Name tests for the behavior and assert the result users rely on.",
        "What does an assertion communicate in a unit test?",
    ),
    _lesson(
        "solid",
        "SOLID principles and maintainable design",
        "Advanced",
        "Use design principles to keep responsibilities focused and dependencies flexible.",
        "SOLID is a set of design heuristics: single responsibility, open-closed, "
        "Liskov substitution, interface segregation, and dependency inversion. "
        "They are not rules to apply mechanically. Start with a clear change in "
        "requirements, then separate responsibilities only when it improves "
        "cohesion, testability, or the cost of change.",
        'interface Notifier {\n    void send(String recipient, String message);\n}\n\nclass ReminderService {\n    private final Notifier notifier;\n    ReminderService(Notifier notifier) { this.notifier = notifier; }\n    void remind(String recipient) { notifier.send(recipient, "Keep learning"); }\n}',
        "Refactor a service so it depends on an interface instead of constructing a concrete notifier.",
        "Inject the dependency so tests can substitute a controlled implementation.",
        "Which SOLID principle recommends depending on abstractions?",
    ),
    _lesson(
        "design-patterns",
        "Object-oriented design patterns",
        "Advanced",
        "Recognize patterns as tools for recurring design problems, not templates to force.",
        "Patterns describe proven structures for recurring trade-offs. Strategy "
        "encapsulates interchangeable algorithms; Factory centralizes object "
        "creation when construction varies; Observer notifies subscribers of "
        "changes. Prefer straightforward code when a pattern adds more indirection "
        "than value.",
        'interface Discount {\n    int applyTo(int cents);\n}\n\nclass NoDiscount implements Discount {\n    public int applyTo(int cents) { return cents; }\n}\n\nclass Checkout {\n    int total(int cents, Discount discount) { return discount.applyTo(cents); }\n}',
        "Use a Strategy interface to support two interchangeable pricing rules.",
        "Keep each strategy small and let the caller select the behavior.",
        "Which pattern encapsulates interchangeable algorithms behind one interface?",
    ),
    _lesson(
        "concurrency",
        "Concurrency with executors and futures",
        "Advanced",
        "Run tasks concurrently while managing their lifecycle and results.",
        "Concurrency lets tasks make progress during overlapping time periods. "
        "ExecutorService manages worker threads; submit returns a Future for a "
        "result. Shut down the executor when finished and use thread-safe designs "
        "for shared mutable state. Prefer higher-level concurrency utilities to "
        "manually managing raw threads.",
        'import java.util.concurrent.ExecutorService;\nimport java.util.concurrent.Executors;\n\npublic class Main {\n    public static void main(String[] args) {\n        ExecutorService pool = Executors.newSingleThreadExecutor();\n        pool.submit(() -> System.out.println("Task completed"));\n        pool.shutdown();\n    }\n}',
        "Submit a background task and collect its result through a Future.",
        "Choose an executor suited to the workload and ensure it is shut down.",
        "What does an ExecutorService manage for an application?",
    ),
    _lesson(
        "jvm-memory",
        "JVM memory, garbage collection, and profiling",
        "Advanced",
        "Understand object lifetime and measure performance before optimizing.",
        "The JVM allocates objects and reclaims unreachable memory with garbage "
        "collection. A memory leak can still occur when a reachable object is "
        "retained unnecessarily. Use profiling and runtime metrics to find evidence "
        "before tuning; do not assume that frequent garbage collection alone proves "
        "a leak.",
        'import java.util.ArrayList;\nimport java.util.List;\n\npublic class Main {\n    public static void main(String[] args) {\n        List<Integer> values = new ArrayList<>();\n        for (int i = 0; i < 1_000; i++) values.add(i);\n        System.out.println(values.size());\n    }\n}',
        "Describe how you would investigate unexpectedly growing memory use in a Java application.",
        "Look for retained references and capture profiling evidence before changing code.",
        "Can garbage collection reclaim an object that is still reachable?",
    ),
    _lesson(
        "maven",
        "Maven, project structure, and dependencies",
        "Advanced",
        "Organize a Java application as a reproducible build.",
        "Maven describes a project in pom.xml, resolves declared dependencies, "
        "compiles source, runs tests, and packages artifacts. Keep application "
        "code under src/main/java and tests under src/test/java. Pin or constrain "
        "dependencies deliberately, review updates, and never commit credentials "
        "in a build file.",
        'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Maven projects describe builds in pom.xml");\n    }\n}',
        "Create a Maven project, add a small domain class, and run its tests.",
        "Use the standard source directories so Maven plugins find code and tests.",
        "Which file is Maven's main project configuration?",
    ),
    _lesson(
        "capstone",
        "Capstone: design an object-oriented library",
        "Advanced",
        "Bring Java fundamentals, OOP, collections, testing, and project structure together.",
        "Design a small library catalog with Book, Member, and Library concepts. "
        "Give each class one clear responsibility, protect its invariants, use "
        "composition for collaborators, and define interfaces only where they "
        "support a real variation. Add tests for successful operations and failure "
        "cases; keep persistence outside the core domain model.",
        'import java.util.HashMap;\nimport java.util.Map;\n\nclass Library {\n    private final Map<String, String> titlesByIsbn = new HashMap<>();\n    void add(String isbn, String title) {\n        if (titlesByIsbn.putIfAbsent(isbn, title) != null) {\n            throw new IllegalArgumentException("ISBN already exists");\n        }\n    }\n    String findTitle(String isbn) { return titlesByIsbn.get(isbn); }\n}',
        "Build a tested catalog that adds, finds, and removes books without exposing its internal map.",
        "Start with the model's invariants and test behavior before adding persistence or a user interface.",
        "Why should Library avoid returning its mutable internal map?",
    ),
]
