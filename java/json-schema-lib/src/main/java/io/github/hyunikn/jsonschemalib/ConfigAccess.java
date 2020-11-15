package io.github.hyunikn.jsonschemalib;

public interface ConfigAccess {
    String getSchema();
    void prettyPrint(StringBuffer sbuf, JsonSchema.PrintMode mode, long selectionBits, String key);
    JsonSchema.SetErr update(int targetRev, String key, String newValJSON, boolean checkOnly, boolean save,
            Object[] onVal, StringBuffer errMsg);
    JsonSchema.SetErr insertArrElem(int targetRev, String key, int idx, String newValJSON, boolean checkOnly,
            boolean save, Object[] onVal, StringBuffer errMsg);
    JsonSchema.SetErr removeArrElem(int targetRev, String key, int idx, boolean checkOnly, boolean save,
            Object[] onVal, StringBuffer errMsg);
}
