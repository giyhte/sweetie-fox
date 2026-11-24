package dcode.module;

public enum Category {
    COMBAT("Бой"), MOVEMENT("Движение"), RENDER("Визуал"), MISC("Прочее");

    public final String title;
    Category(String title) { this.title = title; }
}
