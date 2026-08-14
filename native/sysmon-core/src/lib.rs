use std::cmp::Ordering;
use std::sync::{Mutex, OnceLock};

use pyo3::prelude::*;
use pyo3::types::PyDict;
use sysinfo::{ProcessesToUpdate, System};

static SYSTEM: OnceLock<Mutex<System>> = OnceLock::new();

fn system() -> &'static Mutex<System> {
    SYSTEM.get_or_init(|| Mutex::new(System::new()))
}

#[pyfunction]
#[pyo3(signature = (limit, sort_by, name_filter=None))]
fn list_processes(
    py: Python<'_>,
    limit: usize,
    sort_by: &str,
    name_filter: Option<&str>,
) -> PyResult<Vec<Py<PyAny>>> {
    if limit == 0 {
        return Ok(Vec::new());
    }

    let mut sys = system()
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    sys.refresh_memory();
    sys.refresh_processes(ProcessesToUpdate::All, true);

    let total_memory = sys.total_memory().max(1) as f64;
    let needle = name_filter.map(str::to_lowercase);
    let sort_memory = sort_by == "memory";

    let mut rows: Vec<(f64, f64, i32, String, f64)> = Vec::new();
    for (pid, proc) in sys.processes() {
        let name = proc.name().to_string_lossy().into_owned();
        if let Some(ref needle) = needle {
            if !name.to_lowercase().contains(needle) {
                continue;
            }
        }
        let cpu = f64::from(proc.cpu_usage());
        let mem_bytes = proc.memory() as f64;
        rows.push((
            cpu,
            mem_bytes / total_memory * 100.0,
            pid.as_u32() as i32,
            name,
            mem_bytes / (1024.0 * 1024.0),
        ));
    }

    rows.sort_by(|left, right| {
        let (lhs, rhs) = if sort_memory {
            (left.1, right.1)
        } else {
            (left.0, right.0)
        };
        rhs.partial_cmp(&lhs).unwrap_or(Ordering::Equal)
    });
    rows.truncate(limit);

    let mut out = Vec::with_capacity(rows.len());
    for (cpu, mem_pct, pid, name, mem_mb) in rows {
        let dict = PyDict::new(py);
        dict.set_item("pid", pid)?;
        dict.set_item("name", name)?;
        dict.set_item("cpu_percent", cpu)?;
        dict.set_item("memory_percent", mem_pct)?;
        dict.set_item("memory_mb", mem_mb)?;
        out.push(dict.into_any().unbind());
    }
    Ok(out)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(list_processes, m)?)?;
    Ok(())
}
